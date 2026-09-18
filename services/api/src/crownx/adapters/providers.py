"""ProviderRouter (ADR-016): the one place configuration becomes an embedder and an answerer.

Everything else (domain logic, API contracts, the evaluation runner and the UI) sees only the
`Embedder` and `Answerer` ports plus a description of what's active, so switching MockProvider,
BedrockProvider or GroqProvider is a configuration change. config.py has already refused any provider
the environment doesn't allow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crownx.adapters.ports import Answerer, Embedder
from crownx.config import Settings
from crownx.domain.retrieval import EmbeddingNamespace

TITAN_V2_DIMENSIONS = 1024


@dataclass(frozen=True)
class Providers:
    environment: str
    embedder: Embedder
    namespace: EmbeddingNamespace
    answerer: Answerer | None  # None when Bedrock is selected but no answer model is configured

    def describe(self) -> dict:
        """What /health and the UI show: names and model IDs, never keys or endpoints."""
        return {
            "environment": self.environment,
            "answer_provider": self.answerer.provider if self.answerer else "none",
            "answer_model": self.answerer.model_id if self.answerer else None,
            "embedding_provider": self.namespace.provider,
            "embedding_model": self.namespace.model,
            "embedding_version": self.namespace.version,
        }


class ProviderRouter:
    @staticmethod
    def build(settings: Settings, session: Any = None) -> Providers:
        """`session` is a boto3 Session; only the Bedrock providers use it."""
        embedder, namespace = ProviderRouter._embedding(settings, session)
        return Providers(
            environment=settings.environment,
            embedder=embedder,
            namespace=namespace,
            answerer=ProviderRouter._answering(settings, session),
        )

    @staticmethod
    def _embedding(settings: Settings, session: Any) -> tuple[Embedder, EmbeddingNamespace]:
        if settings.embedding_provider == "mock":
            from crownx.adapters.mock import MOCK_EMBEDDING_MODEL, MockEmbedder

            embedder: Embedder = MockEmbedder(TITAN_V2_DIMENSIONS)
            model = MOCK_EMBEDDING_MODEL
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
            from crownx.adapters.groq import GroqAnswerer

            assert settings.groq_api_key and settings.groq_model_id  # checked by Settings
            return GroqAnswerer(
                api_key=settings.groq_api_key.get_secret_value(),
                model_id=settings.groq_model_id,
                base_url=settings.groq_base_url,
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
