"""Environment settings, validated once per cold start. Names are listed in docs/ARCHITECTURE.md §11.

Providers are chosen here and nowhere else (ADR-016): switching between Bedrock, the mock and Groq is a
configuration change only. The rules below refuse to start with a combination the environment doesn't
allow, so a mock can never answer in production.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["production", "development", "test", "offline-demo"]
AnswerProvider = Literal["bedrock", "mock", "groq"]
EmbeddingProvider = Literal["bedrock", "mock"]

# Which providers each environment may use. Bedrock is the only production provider; the mock is for
# development, tests and an explicit offline demo; Groq (a network call to a third party) only for
# development and tests.
ALLOWED_ANSWER_PROVIDERS: dict[str, set[str]] = {
    "production": {"bedrock"},
    "development": {"bedrock", "mock", "groq"},
    "test": {"bedrock", "mock", "groq"},
    "offline-demo": {"mock"},
}
ALLOWED_EMBEDDING_PROVIDERS: dict[str, set[str]] = {
    "production": {"bedrock"},
    "development": {"bedrock", "mock"},
    "test": {"bedrock", "mock"},
    "offline-demo": {"mock"},
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="ignore")

    environment: Environment = "production"
    answer_provider: AnswerProvider = "bedrock"
    embedding_provider: EmbeddingProvider = "bedrock"
    # Bumped when chunking or embedding parameters change, so old vectors stay out of new queries.
    embedding_version: str = Field(default="1", min_length=1, max_length=16)

    aws_region: str
    documents_bucket: str
    table_name: str
    opensearch_endpoint: str
    opensearch_index: str = "crownx-chunks"
    ingest_function_name: str
    bedrock_embedding_model_id: str
    # ADR-013 is still proposed: the answer model is whatever the stack's AnswerModelId says.
    bedrock_answer_model_id: str | None = None
    # Some Bedrock models can't be forced to call a tool; then `auto` plus an instruction is used.
    bedrock_answer_force_tool: bool = True

    groq_api_key: SecretStr | None = None
    groq_model_id: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"

    max_upload_bytes: int = Field(default=5 * 1024 * 1024, gt=0)
    max_documents_per_workspace: int = Field(default=20, gt=0)
    retrieval_top_k: int = Field(default=8, gt=0, le=50)
    retrieval_score_floor: float = Field(default=0.0, ge=0.0)
    upload_url_expiry_seconds: int = Field(default=300, gt=0, le=3600)

    @model_validator(mode="after")
    def _providers_fit_the_environment(self) -> Settings:
        if self.answer_provider not in ALLOWED_ANSWER_PROVIDERS[self.environment]:
            raise ValueError(
                f"answer provider {self.answer_provider!r} isn't allowed in {self.environment!r}"
            )
        if self.embedding_provider not in ALLOWED_EMBEDDING_PROVIDERS[self.environment]:
            raise ValueError(
                f"embedding provider {self.embedding_provider!r} isn't allowed in "
                f"{self.environment!r}"
            )
        if self.answer_provider == "groq" and not (self.groq_api_key and self.groq_model_id):
            raise ValueError("the groq answer provider needs GROQ_API_KEY and GROQ_MODEL_ID")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
