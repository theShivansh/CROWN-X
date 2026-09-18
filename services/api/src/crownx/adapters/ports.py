"""What the application needs from storage, search and compute, independent of AWS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from crownx.domain.answering import AnswerDraft
from crownx.domain.models import Document, DocumentStatus, QueryRecord, Workspace


@dataclass(frozen=True)
class ObjectInfo:
    size_bytes: int
    content_type: str | None


class MetadataStore(Protocol):
    """DynamoDB single table: `PK = WS#{ws}`; `SK` is `META`, `DOC#{doc}`, `CHECKSUM#{sha256}`,
    `QUERY#{query_id}` or `AUDIT#{iso-ts}#{request_id}`."""

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

    def put_query(self, record: QueryRecord) -> None:
        """Write once; a query record is never updated."""
        ...

    def get_query(self, workspace_id: str, query_id: str) -> QueryRecord | None: ...

    def put_audit(self, workspace_id: str, event: dict) -> None:
        """IDs, stages, timings and outcomes only: never document text or model output."""
        ...


class ObjectStore(Protocol):
    def presigned_post(
        self, key: str, content_type: str, max_bytes: int, expires_in: int
    ) -> dict: ...

    def head(self, key: str) -> ObjectInfo | None: ...

    def sha256(self, key: str) -> str: ...

    def read_bytes(self, key: str) -> bytes: ...

    def ping(self) -> None: ...


class IngestQueue(Protocol):
    def enqueue(self, workspace_id: str, document_id: str) -> None: ...


class Embedder(Protocol):
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per text, in order."""
        ...


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    score: float
    source: dict


class SearchIndex(Protocol):
    def index_exists(self) -> bool:
        """False when the index hasn't been created; raises when the store is unreachable."""
        ...

    def ensure_index(self, body: dict) -> bool:
        """Create the index if it's missing; True when this call created it."""
        ...

    def index_chunks(self, chunks: list[dict]) -> None:
        """Write chunks by `chunk_id` and return once they're searchable."""
        ...

    def search(self, body: dict) -> list[SearchHit]: ...


@dataclass(frozen=True)
class AnswerResult:
    draft: AnswerDraft
    provider: str
    model_id: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    invocation_id: str | None = None


class Answerer(Protocol):
    """One answer call over exactly the evidence given. Providers: ADR-016."""

    provider: str
    model_id: str

    def answer(self, question: str, evidence: list[dict]) -> AnswerResult:
        """Raise `ModelTimeout` after its own bounded retry, `AnswerUnavailable` when refused."""
        ...
