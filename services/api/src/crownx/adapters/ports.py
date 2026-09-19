"""What the application needs from storage, search and compute, independent of AWS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from crownx.domain.answering import AnswerDraft
from crownx.domain.claims import Claim
from crownx.domain.events import WorkflowEvent
from crownx.domain.models import Document, DocumentStatus, QueryRecord, Workspace


@dataclass(frozen=True)
class ObjectInfo:
    size_bytes: int
    content_type: str | None


class MetadataStore(Protocol):
    """DynamoDB single table: `PK = WS#{ws}`; `SK` is `META`, `DOC#{doc}`, `CHECKSUM#{sha256}`,
    `QUERY#{query_id}`, `AUDIT#{iso-ts}#{request_id}`, `EVENT#{iso-ts}#{event_id}` or
    `CLAIM#{subject}#{attribute}#{claim_id}`."""

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

    def count_usage(self, workspace_id: str, kind: str, window: str, expires_at: int) -> int:
        """Add one to the workspace's `kind` counter for `window` atomically and return the new
        count. The item expires at `expires_at` (epoch seconds, DynamoDB TTL)."""
        ...

    def put_event(self, event: WorkflowEvent) -> None:
        """Append to the workspace's event stream; idempotent by `event_id` (FR-WL-01)."""
        ...

    def list_events(self, workspace_id: str, limit: int = 2000) -> list[WorkflowEvent]:
        """The newest `limit` events of one workspace, oldest first."""
        ...

    def claim_event_id(self, workspace_id: str, event_id: str) -> bool:
        """Reserve a client event ID; False when it was already recorded (a retry)."""
        ...

    def get_workflow_states(self, workspace_id: str) -> dict[str, dict]:
        """What's stored about each workflow suggestion (name, dismissal), by suggestion ID."""
        ...

    def put_workflow_state(self, workspace_id: str, suggestion_id: str, state: dict) -> None: ...

    def add_template(self, workspace_id: str, suggestion_id: str, template: dict) -> int:
        """Write the next immutable version of a saved workflow and return its version number."""
        ...

    def list_templates(self, workspace_id: str) -> list[dict]: ...

    def replace_claims(self, workspace_id: str, document_id: str, claims: list[Claim]) -> None:
        """Delete the document's previous claims, then write these (M3, ADR-020): a re-ingested
        document leaves nothing stale, and conflicts are derived from the claims when read."""
        ...

    def list_claims(self, workspace_id: str) -> list[Claim]: ...


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

    def embed(self, texts: list[str], kind: str = "passage") -> list[list[float]]:
        """One vector per text, in order. `kind` is "query" or "passage": some models (E5, BGE)
        embed a question differently from the text that answers it."""
        ...


class Reranker(Protocol):
    """A cross-encoder that re-orders retrieved passages for one question (ADR-017)."""

    model_id: str

    def scores(self, question: str, passages: list[str]) -> list[float]:
        """One relevance score per passage, in order; higher is more relevant."""
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
    # Every model call made for this answer, in order: {"model_id", "outcome"}. `model_id` above is
    # the one that answered, which differs from the configured model after a fallback.
    attempts: tuple[dict, ...] = ()


class Answerer(Protocol):
    """One answer call over exactly the evidence given. Providers: ADR-016."""

    provider: str
    model_id: str

    def answer(
        self, question: str, evidence: list[dict], conflicts: list[dict] | None = None
    ) -> AnswerResult:
        """Raise `ModelTimeout` after its own bounded retry, `AnswerUnavailable` when refused.
        `conflicts`: the groups code detected on the retrieved evidence (M3), passed as data."""
        ...
