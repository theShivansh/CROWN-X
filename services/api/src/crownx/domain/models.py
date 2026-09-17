"""Records shared by the API, ingestion and storage adapters (SRS §4)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> str:
    """ISO 8601 in UTC with a `Z`, sortable as a string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class DocumentStatus(StrEnum):
    PENDING = "pending"  # upload URL issued, object not confirmed
    QUEUED = "queued"  # object confirmed, ingestion invoked
    PARSING = "parsing"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    DUPLICATE = "duplicate"  # same checksum as `duplicate_of` in this workspace


class Workspace(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace_id: str
    created_at: str


class Document(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str
    workspace_id: str
    filename: str
    content_type: str
    size_bytes: int = Field(ge=0)
    object_key: str
    status: DocumentStatus
    # The stage the document is in, or the one it failed in.
    stage: DocumentStatus
    uploaded_at: str
    checksum: str | None = None
    error: str | None = None
    duplicate_of: str | None = None
    chunk_count: int | None = None
    version_label: str | None = None
    source_timestamp: str | None = None

    def public(self) -> dict:
        """The API view: storage keys stay server-side."""
        return self.model_dump(mode="json", exclude={"object_key"})
