"""What the application needs from storage, search and compute, independent of AWS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from crownx.domain.models import Document, DocumentStatus, Workspace


@dataclass(frozen=True)
class ObjectInfo:
    size_bytes: int
    content_type: str | None


class MetadataStore(Protocol):
    """DynamoDB single table: `PK = WS#{ws}`; `SK` is `META`, `DOC#{doc}` or `CHECKSUM#{sha256}`."""

    def put_workspace(self, workspace: Workspace) -> None: ...

    def get_workspace(self, workspace_id: str) -> Workspace | None: ...

    def put_document(self, document: Document) -> None: ...

    def get_document(self, workspace_id: str, document_id: str) -> Document | None: ...

    def list_documents(self, workspace_id: str) -> list[Document]: ...

    def replace_document(self, document: Document, expected_status: DocumentStatus) -> bool:
        """Write `document` only if the stored status is still `expected_status`."""
        ...

    def claim_checksum(self, workspace_id: str, checksum: str, document_id: str) -> str:
        """Record the checksum for `document_id` unless it exists; return the owning document ID."""
        ...


class ObjectStore(Protocol):
    def presigned_post(
        self, key: str, content_type: str, max_bytes: int, expires_in: int
    ) -> dict: ...

    def head(self, key: str) -> ObjectInfo | None: ...

    def sha256(self, key: str) -> str: ...

    def ping(self) -> None: ...


class IngestQueue(Protocol):
    def enqueue(self, workspace_id: str, document_id: str) -> None: ...


class SearchIndex(Protocol):
    def index_exists(self) -> bool:
        """False when the index hasn't been created; raises when the store is unreachable."""
        ...
