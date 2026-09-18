"""ADR-016 and ADR-017: providers are chosen by configuration only; production answers with Groq (or
Bedrock) and embeds with the local ONNX model (or Bedrock), never the mock; and embeddings from
different providers never meet in one query."""

from __future__ import annotations

import pytest
from conftest import MAX_BYTES, NAMESPACE
from fakes import FakeIndex, FakeIngest, FakeObjects, FakeStore
from pydantic import ValidationError

from crownx.adapters.bedrock import TitanEmbedder
from crownx.adapters.bedrock_answer import ConverseAnswerer
from crownx.adapters.groq import GroqAnswerer
from crownx.adapters.mock import MockAnswerer, MockEmbedder
from crownx.adapters.providers import ProviderRouter
from crownx.app.ingestion import IngestionWorker
from crownx.app.service import CrownService, Limits
from crownx.config import Settings
from crownx.domain.retrieval import EmbeddingNamespace

BASE = {
    "aws_region": "ap-south-1",
    "documents_bucket": "b",
    "table_name": "t",
    "opensearch_endpoint": "search.example.test",
    "ingest_function_name": "crownx-ingest",
    "bedrock_embedding_model_id": "amazon.titan-embed-text-v2:0",
}
GROQ = {"groq_model_id": "openai/gpt-oss-120b", "groq_api_key_parameter": "/crownx/groq-api-key"}
ONNX = {"onnx_model_uri": "s3://bucket/models/e5/", "onnx_model_sha256": "0" * 64}
BEDROCK = {"answer_provider": "bedrock", "embedding_provider": "bedrock"}


def settings(**overrides) -> Settings:
    return Settings(**{**BASE, **overrides})


class FakeSession:
    def __init__(self) -> None:
        self.clients: list[tuple[str, object]] = []

    def client(self, name: str, config: object = None) -> object:
        self.clients.append((name, config))
        return object()


# ---------------------------------------------------------------- which provider each environment may use


def test_production_defaults_to_groq_answers_and_onnx_embeddings():
    s = settings(**GROQ, **ONNX)
    assert (s.environment, s.answer_provider, s.embedding_provider, s.groq_transport) == (
        "production",
        "groq",
        "onnx",
        "http",
    )


def test_production_may_still_choose_bedrock():
    s = settings(**BEDROCK)
    assert (s.answer_provider, s.embedding_provider) == ("bedrock", "bedrock")


@pytest.mark.parametrize(
    "overrides",
    [
        {"answer_provider": "mock", "embedding_provider": "bedrock"},
        {"answer_provider": "bedrock", "embedding_provider": "mock"},
    ],
)
def test_production_refuses_the_mock(overrides):
    with pytest.raises(ValidationError, match="isn't allowed in 'production'"):
        settings(environment="production", **overrides)


def test_production_refuses_the_scripted_groq_transport():
    with pytest.raises(ValidationError, match="groq transport 'mock' isn't allowed"):
        settings(**GROQ, **ONNX, groq_transport="mock")


def test_onnx_needs_a_pinned_model():
    with pytest.raises(ValidationError, match="ONNX_MODEL_URI and ONNX_MODEL_SHA256"):
        settings(**GROQ, onnx_model_uri="s3://bucket/models/e5/")


def test_the_reranker_needs_a_pinned_model_when_enabled():
    with pytest.raises(ValidationError, match="RERANKER_MODEL_URI"):
        settings(**BEDROCK, reranker_enabled=True)


@pytest.mark.parametrize(
    "overrides",
    [{"answer_provider": "bedrock"}, {"embedding_provider": "bedrock", "answer_provider": "mock"}],
)
def test_offline_demo_is_mock_only(overrides):
    with pytest.raises(ValidationError, match="isn't allowed in 'offline-demo'"):
        settings(environment="offline-demo", **{"embedding_provider": "mock", **overrides})


def test_offline_demo_answers_with_the_mock_only():
    with pytest.raises(ValidationError, match="answer provider 'groq' isn't allowed"):
        settings(environment="offline-demo", embedding_provider="mock", **GROQ)


@pytest.mark.parametrize("environment", ["development", "test", "offline-demo"])
def test_the_mock_is_allowed_outside_production(environment):
    s = settings(environment=environment, answer_provider="mock", embedding_provider="mock")
    assert s.answer_provider == "mock"


def test_groq_needs_its_model_and_a_key_source_and_never_leaks_the_key():
    with pytest.raises(ValidationError, match="GROQ_MODEL_ID"):
        settings(environment="development", embedding_provider="mock")
    with pytest.raises(ValidationError, match="GROQ_API_KEY or GROQ_API_KEY_PARAMETER"):
        settings(environment="development", embedding_provider="mock", groq_model_id="m")
    s = settings(
        environment="development",
        embedding_provider="mock",
        groq_api_key="gsk_secret",
        groq_model_id="m",
    )
    assert "gsk_secret" not in repr(s)


def test_the_scripted_transport_needs_no_key():
    s = settings(
        environment="test", embedding_provider="mock", groq_model_id="m", groq_transport="mock"
    )
    assert s.groq_api_key is None


# ---------------------------------------------------------------- the router


def test_router_builds_the_mock_provider_without_touching_aws():
    providers = ProviderRouter.build(
        settings(environment="offline-demo", answer_provider="mock", embedding_provider="mock"),
        session=None,
    )
    assert isinstance(providers.embedder, MockEmbedder)
    assert isinstance(providers.answerer, MockAnswerer)
    assert providers.namespace == EmbeddingNamespace("mock", "mock-hashed-bow", "1", 384)
    assert providers.describe() == {
        "environment": "offline-demo",
        "answer_provider": "mock",
        "answer_model": "mock-extractive",
        "answer_fallback_model": None,
        "embedding_provider": "mock",
        "embedding_model": "mock-hashed-bow",
        "embedding_version": "1",
        "reranker_model": None,
    }


def test_router_builds_bedrock_with_the_configured_models_only():
    session = FakeSession()
    providers = ProviderRouter.build(
        settings(**BEDROCK, bedrock_answer_model_id="qwen.qwen3-235b-a22b-2507-v1:0"), session
    )
    assert isinstance(providers.embedder, TitanEmbedder)
    assert isinstance(providers.answerer, ConverseAnswerer)
    assert providers.answerer.model_id == "qwen.qwen3-235b-a22b-2507-v1:0"
    assert providers.namespace == EmbeddingNamespace(
        "bedrock", "amazon.titan-embed-text-v2:0", "1", 1024
    )
    assert [name for name, _ in session.clients] == ["bedrock-runtime", "bedrock-runtime"]
    answer_config = session.clients[1][1]
    assert answer_config.read_timeout == 12 and answer_config.retries == {"max_attempts": 1}


def test_bedrock_without_an_answer_model_has_no_answerer_and_says_so():
    providers = ProviderRouter.build(settings(**BEDROCK, bedrock_answer_model_id=""), FakeSession())
    assert providers.answerer is None
    assert providers.describe()["answer_provider"] == "none"


def test_router_builds_groq_for_development():
    providers = ProviderRouter.build(
        settings(
            environment="development",
            answer_provider="groq",
            embedding_provider="mock",
            groq_api_key="gsk_x",
            groq_model_id="llama-3.3-70b-versatile",
        ),
        session=None,
    )
    assert isinstance(providers.answerer, GroqAnswerer)
    assert providers.describe()["answer_model"] == "llama-3.3-70b-versatile"


class FakeSsm:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def get_parameter(self, **request) -> dict:
        self.requests.append(request)
        return {"Parameter": {"Value": "gsk_from_ssm"}}


class SsmSession(FakeSession):
    def __init__(self) -> None:
        super().__init__()
        self.ssm = FakeSsm()

    def client(self, name: str, config: object = None) -> object:
        self.clients.append((name, config))
        return self.ssm if name == "ssm" else object()


def test_production_groq_reads_its_key_from_ssm_once_and_never_describes_it():
    session = SsmSession()
    providers = ProviderRouter.build(
        settings(**GROQ, embedding_provider="bedrock", groq_fallback_model_id="openai/gpt-oss-20b"),
        session,
    )
    assert session.ssm.requests == [{"Name": "/crownx/groq-api-key", "WithDecryption": True}]
    assert isinstance(providers.answerer, GroqAnswerer)
    assert providers.answerer._api_key == "gsk_from_ssm"
    described = providers.describe()
    assert described["answer_provider"] == "groq"
    assert described["answer_model"] == "openai/gpt-oss-120b"
    assert described["answer_fallback_model"] == "openai/gpt-oss-20b"
    assert "gsk_from_ssm" not in repr(described)


def test_the_scripted_transport_builds_without_network_or_key():
    from crownx.adapters.groq_mock import MockGroqTransport

    providers = ProviderRouter.build(
        settings(
            environment="test",
            embedding_provider="mock",
            groq_model_id="openai/gpt-oss-120b",
            groq_transport="mock",
            groq_mock_mode="rate_limited_long",
            groq_fallback_model_id="openai/gpt-oss-20b",
        ),
        session=None,
    )
    assert isinstance(providers.answerer._transport, MockGroqTransport)
    result = providers.answerer.answer("When is the deadline?", [])
    assert result.model_id == "openai/gpt-oss-20b"  # the scripted 429 sent it to the fallback


# ---------------------------------------------------------------- configuration-only switching, one shared index


def _service(store, objects, index, providers) -> tuple[CrownService, IngestionWorker]:
    service = CrownService(
        store=store,
        objects=objects,
        ingest=FakeIngest(),
        index=index,
        embedder=providers.embedder,
        namespace=providers.namespace,
        answerer=providers.answerer,
        providers=providers.describe(),
        limits=Limits(
            max_upload_bytes=MAX_BYTES,
            max_documents_per_workspace=5,
            upload_url_expiry_seconds=300,
            retrieval_top_k=4,
        ),
    )
    worker = IngestionWorker(store, objects, providers.embedder, index, providers.namespace)
    return service, worker


def _upload(service, worker, objects, ws, name, content):
    ticket = service.create_upload(ws, name, len(content))
    objects.objects[ticket.document.object_key] = content
    service.complete_upload(ws, ticket.document.document_id)
    worker.ingest(ws, ticket.document.document_id)


def test_the_whole_pipeline_runs_on_the_mock_provider_by_configuration_alone():
    store, objects, index = FakeStore(), FakeObjects(), FakeIndex()
    providers = ProviderRouter.build(
        settings(environment="test", answer_provider="mock", embedding_provider="mock"), None
    )
    service, worker = _service(store, objects, index, providers)
    ws = service.create_workspace().workspace_id
    _upload(
        service,
        worker,
        objects,
        ws,
        "brief.md",
        b"# Timeline\n\nFinal submissions close on 20 September 2026.\n",
    )

    query = service.query(ws, "When do final submissions close?")
    outcome = service.answer(ws, query.query_id)

    assert query.status == "retrieved"
    assert {c["embedding_provider"] for c in index.chunks.values()} == {"mock"}
    assert outcome.final.status == "grounded"
    assert outcome.provider == "mock"
    assert "20 September 2026" in outcome.final.answer
    cited = {i for claim in outcome.final.claims for i in claim["evidence_ids"]}
    assert cited <= {e["evidence_id"] for e in query.evidence}


def test_chunks_from_one_embedding_namespace_never_answer_another():
    store, objects, index = FakeStore(), FakeObjects(), FakeIndex()
    mock = ProviderRouter.build(
        settings(environment="test", answer_provider="mock", embedding_provider="mock"), None
    )
    mock_service, mock_worker = _service(store, objects, index, mock)
    ws = mock_service.create_workspace().workspace_id
    _upload(
        mock_service,
        mock_worker,
        objects,
        ws,
        "brief.md",
        b"Final submissions close on 20 September 2026.\n",
    )

    # Same workspace, same index, same vector size: only the namespace differs.
    other = type(mock)(
        environment="test",
        embedder=MockEmbedder(384),
        namespace=EmbeddingNamespace("bedrock", "amazon.titan-embed-text-v2:0", "1", 384),
        answerer=MockAnswerer(),
    )
    other_service, _ = _service(store, objects, index, other)
    result = other_service.query(ws, "When do final submissions close?")
    assert result.status == "insufficient_evidence" and result.evidence == []
    assert NAMESPACE.provider == "fake"  # the shared harness uses its own namespace too
