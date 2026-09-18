"""ProviderRouter (ADR-016, ADR-017): the one place configuration becomes an embedder, an answerer and
an optional reranker.

Everything else (domain logic, API contracts, the evaluation runner and the UI) sees only the
`Embedder`, `Answerer` and `Reranker` ports plus a description of what's active, so switching between
the Groq, ONNX, Bedrock and mock providers is a configuration change. config.py has already refused any
provider the environment doesn't allow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crownx.adapters.ports import Answerer, Embedder, Reranker
from crownx.config import Settings
from crownx.domain.retrieval import EmbeddingNamespace

TITAN_V2_DIMENSIONS = 1024
MOCK_DIMENSIONS = 384  # the ONNX models' size, so the mock can share the production index


@dataclass(frozen=True)
class Providers:
    environment: str
    embedder: Embedder
    namespace: EmbeddingNamespace
    answerer: Answerer | None  # None when Bedrock is selected but no answer model is configured
    reranker: Reranker | None = None

    def describe(self) -> dict:
        """What /health, the logs, the audit and the UI show: names and model IDs, never keys or
        endpoints."""
        return {
            "environment": self.environment,
            "answer_provider": self.answerer.provider if self.answerer else "none",
            "answer_model": self.answerer.model_id if self.answerer else None,
            "answer_fallback_model": getattr(self.answerer, "fallback_model_id", None),
            "embedding_provider": self.namespace.provider,
            "embedding_model": self.namespace.model,
            "embedding_version": self.namespace.version,
            "reranker_model": self.reranker.model_id if self.reranker else None,
        }


class ProviderRouter:
    @staticmethod
    def build(settings: Settings, session: Any = None) -> Providers:
        """`session` is a boto3 Session; the Bedrock providers, SSM and S3 model downloads use it."""
        embedder, namespace = ProviderRouter._embedding(settings, session)
        return Providers(
            environment=settings.environment,
            embedder=embedder,
            namespace=namespace,
            answerer=ProviderRouter._answering(settings, session),
            reranker=ProviderRouter._reranking(settings, session),
        )

    @staticmethod
    def _embedding(settings: Settings, session: Any) -> tuple[Embedder, EmbeddingNamespace]:
        if settings.embedding_provider == "mock":
            from crownx.adapters.mock import MOCK_EMBEDDING_MODEL, MockEmbedder

            embedder: Embedder = MockEmbedder(MOCK_DIMENSIONS)
            model = MOCK_EMBEDDING_MODEL
        elif settings.embedding_provider == "onnx":
            from crownx.adapters.onnx_models import OnnxEmbedder, resolve_model_dir

            assert settings.onnx_model_uri and settings.onnx_model_sha256  # checked by Settings
            directory = resolve_model_dir(
                settings.onnx_model_uri,
                settings.onnx_model_name,
                settings.onnx_model_sha256,
                _s3(session, settings.onnx_model_uri),
            )
            embedder = OnnxEmbedder(directory, settings.onnx_model_name)
            model = settings.onnx_model_name
        else:
            from crownx.adapters.bedrock import TitanEmbedder

            embedder = TitanEmbedder(
                session.client("bedrock-runtime"),
                settings.bedrock_embedding_model_id,
                dimensions=TITAN_V2_DIMENSIONS,
            )
            model = settings.bedrock_embedding_model_id
        return embedder, EmbeddingNamespace(
            provider=settings.embedding_provider,
            model=model,
            version=settings.embedding_version,
            dimensions=embedder.dimensions,
        )

    @staticmethod
    def _answering(settings: Settings, session: Any) -> Answerer | None:
        if settings.answer_provider == "mock":
            from crownx.adapters.mock import MockAnswerer

            return MockAnswerer()
        if settings.answer_provider == "groq":
            from crownx.adapters.groq import GroqAnswerer, urllib_transport

            assert settings.groq_model_id  # checked by Settings
            if settings.groq_transport == "mock":
                from crownx.adapters.groq_mock import MockGroqTransport

                return GroqAnswerer(
                    api_key="mock",
                    model_id=settings.groq_model_id,
                    fallback_model_id=settings.groq_fallback_model_id,
                    transport=MockGroqTransport(settings.groq_mock_mode),
                    sleep=lambda _seconds: None,
                )
            return GroqAnswerer(
                api_key=_groq_key(settings, session),
                model_id=settings.groq_model_id,
                fallback_model_id=settings.groq_fallback_model_id,
                base_url=settings.groq_base_url,
                transport=urllib_transport,
            )
        if not settings.bedrock_answer_model_id:
            return None
        from botocore.config import Config

        from crownx.adapters.bedrock_answer import ConverseAnswerer

        # Two attempts must fit inside API Gateway's 30 s; the adapter does its own single retry.
        config = Config(connect_timeout=3, read_timeout=12, retries={"max_attempts": 1})
        return ConverseAnswerer(
            session.client("bedrock-runtime", config=config),
            settings.bedrock_answer_model_id,
            force_tool=settings.bedrock_answer_force_tool,
        )

    @staticmethod
    def _reranking(settings: Settings, session: Any) -> Reranker | None:
        if not settings.reranker_enabled:
            return None
        from crownx.adapters.onnx_models import OnnxReranker, resolve_model_dir

        assert settings.reranker_model_uri and settings.reranker_model_sha256  # checked by Settings
        directory = resolve_model_dir(
            settings.reranker_model_uri,
            settings.reranker_model_name,
            settings.reranker_model_sha256,
            _s3(session, settings.reranker_model_uri),
        )
        return OnnxReranker(directory, settings.reranker_model_name)


def _s3(session: Any, uri: str) -> Any:
    return session.client("s3") if uri.startswith("s3://") else None


def _groq_key(settings: Settings, session: Any) -> str:
    """The environment's key for local runs; otherwise the SecureString named by the stack."""
    if settings.groq_api_key is not None:
        return settings.groq_api_key.get_secret_value()
    parameter = settings.groq_api_key_parameter
    assert parameter  # checked by Settings
    response = session.client("ssm").get_parameter(Name=parameter, WithDecryption=True)
    return response["Parameter"]["Value"]
