"""Environment settings, validated once per cold start. Names are listed in docs/ARCHITECTURE.md §11."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="ignore")

    aws_region: str
    documents_bucket: str
    table_name: str
    opensearch_endpoint: str
    opensearch_index: str = "crownx-chunks"
    ingest_function_name: str
    bedrock_embedding_model_id: str
    # Used from M2, when the answer call arrives.
    bedrock_answer_model_id: str | None = None

    max_upload_bytes: int = Field(default=5 * 1024 * 1024, gt=0)
    max_documents_per_workspace: int = Field(default=20, gt=0)
    retrieval_top_k: int = Field(default=8, gt=0, le=50)
    upload_url_expiry_seconds: int = Field(default=300, gt=0, le=3600)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
