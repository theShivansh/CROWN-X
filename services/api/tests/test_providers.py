"""ADR-016: providers are chosen by configuration only, Bedrock is the only production provider, and
embeddings from different providers never meet in one query."""

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


def settings(**overrides) -> Settings:
    return Settings(**{**BASE, **overrides})


class FakeSession:
    def __init__(self) -> None:
        self.clients: list[tuple[str, object]] = []

    def client(self, name: str, config: object = None) -> object:
        self.clients.append((name, config))
        return object()


# ---------------------------------------------------------------- which provider each environment may use


def test_production_defaults_to_bedrock_for_both():
    s = settings()
    assert (s.environment, s.answer_provider, s.embedding_provider) == (
        "production",
        "bedrock",
        "bedrock",
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"answer_provider": "mock"},
        {"embedding_provider": "mock"},
        {"answer_provider": "groq", "groq_api_key": "k", "groq_model_id": "m"},
    ],
)
def test_production_refuses_anything_but_bedrock(overrides):
    with pytest.raises(ValidationError, match="isn't allowed in 'production'"):
        settings(environment="production", **overrides)


@pytest.mark.parametrize(
    "overrides",
    [{"answer_provider": "bedrock"}, {"embedding_provider": "bedrock", "answer_provider": "mock"}],
)
def test_offline_demo_is_mock_only(overrides):
    with pytest.raises(ValidationError, match="isn't allowed in 'offline-demo'"):
        settings(environment="offline-demo", **{"embedding_provider": "mock", **overrides})


@pytest.mark.parametrize("environment", ["development", "test", "offline-demo"])
def test_the_mock_is_allowed_outside_production(environment):
    s = settings(environment=environment, answer_provider="mock", embedding_provider="mock")
    assert s.answer_provider == "mock"


def test_groq_needs_its_key_and_model_and_never_leaks_the_key():
    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        settings(environment="development", answer_provider="groq")
    s = settings(
        environment="development",
        answer_provider="groq",
        groq_api_key="gsk_secret",
        groq_model_id="m",
    )
    assert "gsk_secret" not in repr(s)


# ---------------------------------------------------------------- the router


def test_router_builds_the_mock_provider_without_touching_aws():
    providers = ProviderRouter.build(
        settings(environment="offline-demo", answer_provider="mock", embedding_provider="mock"),
        session=None,
    )
    assert isinstance(providers.embedder, MockEmbedder)
    assert isinstance(providers.answerer, MockAnswerer)
    assert providers.namespace == EmbeddingNamespace("mock", "mock-hashed-bow", "1", 1024)
    assert providers.describe() == {
        "environment": "offline-demo",
        "answer_provider": "mock",
        "answer_model": "mock-extractive",
        "embedding_provider": "mock",
        "embedding_model": "mock-hashed-bow",
        "embedding_version": "1",
    }


def test_router_builds_bedrock_with_the_configured_models_only():
    session = FakeSession()
    providers = ProviderRouter.build(
        settings(bedrock_answer_model_id="qwen.qwen3-235b-a22b-2507-v1:0"), session
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
    providers = ProviderRouter.build(settings(bedrock_answer_model_id=""), FakeSession())
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
        embedder=MockEmbedder(1024),
        namespace=EmbeddingNamespace("bedrock", "amazon.titan-embed-text-v2:0", "1", 1024),
        answerer=MockAnswerer(),
    )
    other_service, _ = _service(store, objects, index, other)
    result = other_service.query(ws, "When do final submissions close?")
    assert result.status == "insufficient_evidence" and result.evidence == []
    assert NAMESPACE.provider == "fake"  # the shared harness uses its own namespace too
