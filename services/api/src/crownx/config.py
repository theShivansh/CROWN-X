"""Environment settings, validated once per cold start. Names are listed in docs/ARCHITECTURE.md §11.

Providers are chosen here and nowhere else (ADR-016): switching providers is a configuration change
only. ADR-017 makes Groq (answers) and a local ONNX model (embeddings) the production providers; Bedrock
stays available as an option. The rules below refuse to start with a combination the environment
doesn't allow, so a mock can never answer in production.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["production", "development", "test", "offline-demo"]
AnswerProvider = Literal["bedrock", "mock", "groq"]
EmbeddingProvider = Literal["bedrock", "mock", "onnx"]
GroqTransport = Literal["http", "mock"]

# Which providers each environment may use (ADR-017). Production answers with Groq or Bedrock and
# embeds with the local ONNX model or Bedrock; the mock is for development, tests and an explicit
# offline demo only.
ALLOWED_ANSWER_PROVIDERS: dict[str, set[str]] = {
    "production": {"groq", "bedrock"},
    "development": {"bedrock", "mock", "groq"},
    "test": {"bedrock", "mock", "groq"},
    "offline-demo": {"mock"},
}
ALLOWED_EMBEDDING_PROVIDERS: dict[str, set[str]] = {
    "production": {"onnx", "bedrock"},
    "development": {"bedrock", "mock", "onnx"},
    "test": {"bedrock", "mock", "onnx"},
    "offline-demo": {"mock"},
}
# The scripted Groq transport never reaches the network, so it is never allowed to pass for Groq in
# production (ADR-017).
ALLOWED_GROQ_TRANSPORTS: dict[str, set[str]] = {
    "production": {"http"},
    "development": {"http", "mock"},
    "test": {"http", "mock"},
    "offline-demo": {"http"},  # unused there: offline-demo answers with the mock provider
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="ignore")

    environment: Environment = "production"
    answer_provider: AnswerProvider = "groq"
    embedding_provider: EmbeddingProvider = "onnx"
    # Bumped when chunking or embedding parameters change, so old vectors stay out of new queries.
    embedding_version: str = Field(default="1", min_length=1, max_length=16)

    aws_region: str
    documents_bucket: str
    table_name: str
    opensearch_endpoint: str
    opensearch_index: str = "crownx-chunks"
    ingest_function_name: str

    # Bedrock (optional since ADR-017).
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_answer_model_id: str | None = None
    # Some Bedrock models can't be forced to call a tool; then `auto` plus an instruction is used.
    bedrock_answer_force_tool: bool = True

    # Groq (production answers). In AWS the key is a SecureString in SSM Parameter Store, read once
    # per cold start; GROQ_API_KEY in the environment is for local runs.
    groq_api_key: SecretStr | None = None
    groq_api_key_parameter: str | None = None
    groq_model_id: str | None = None
    groq_fallback_model_id: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_transport: GroqTransport = "http"
    # Scripted behaviour of the mock transport (adapters/groq_mock.py); ignored over http.
    groq_mock_mode: str = "ok"

    # Local ONNX models (ADR-017): `onnx_model_uri` is `s3://bucket/prefix/` or a local directory that
    # holds `model.onnx` and `tokenizer.json`; the model file must match `onnx_model_sha256`. The name
    # picks the pooling and prefixes (adapters/onnx_models.py, EMBEDDING_PROFILES).
    onnx_model_name: str = "bge-small-en-v1.5-int8"
    onnx_model_uri: str | None = None
    onnx_model_sha256: str | None = None
    reranker_enabled: bool = False
    reranker_model_name: str = "ms-marco-MiniLM-L-6-v2-int8"
    reranker_model_uri: str | None = None
    reranker_model_sha256: str | None = None

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
        if self.groq_transport not in ALLOWED_GROQ_TRANSPORTS[self.environment]:
            raise ValueError(
                f"groq transport {self.groq_transport!r} isn't allowed in {self.environment!r}"
            )
        if self.answer_provider == "groq":
            if not self.groq_model_id:
                raise ValueError("the groq answer provider needs GROQ_MODEL_ID")
            configured = self.groq_api_key is not None or bool(self.groq_api_key_parameter)
            if self.groq_transport == "http" and not configured:
                raise ValueError(
                    "the groq answer provider needs GROQ_API_KEY or GROQ_API_KEY_PARAMETER"
                )
        if self.embedding_provider == "onnx" and not (
            self.onnx_model_uri and self.onnx_model_sha256
        ):
            raise ValueError(
                "the onnx embedding provider needs ONNX_MODEL_URI and ONNX_MODEL_SHA256"
            )
        if self.reranker_enabled and not (self.reranker_model_uri and self.reranker_model_sha256):
            raise ValueError("the reranker needs RERANKER_MODEL_URI and RERANKER_MODEL_SHA256")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
