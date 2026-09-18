"""CROWN-native workflow events (FR-WL-01, FR-WL-02; ADR-018).

Written server-side during ingestion and questions into an append-only stream per workspace. An event
holds IDs, a type, a status and timings only: never document text, questions or answers.
"""

from __future__ import annotations

import re
import secrets
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

_EVENT_ID = re.compile(r"evt_[A-Za-z0-9_-]{22}")


class EventType(StrEnum):
    DOCUMENT_UPLOAD_REQUESTED = "document_upload_requested"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_DUPLICATE = "document_duplicate"
    DOCUMENT_INDEXED = "document_indexed"
    DOCUMENT_FAILED = "document_failed"
    QUESTION_ASKED = "question_asked"
    EVIDENCE_RETRIEVED = "evidence_retrieved"
    ANSWER_GENERATED = "answer_generated"
    ANSWER_INSUFFICIENT = "answer_insufficient"
    ANSWER_UNAVAILABLE = "answer_unavailable"


# Equivalent events share one stable step type, so a workflow isn't split by incidental outcomes.
# A duplicate upload is still "a document was added"; a failed ingestion isn't a workflow step.
NORMALIZED: dict[EventType, str | None] = {
    EventType.DOCUMENT_UPLOAD_REQUESTED: None,  # always followed by an upload or nothing at all
    EventType.DOCUMENT_UPLOADED: "add_document",
    EventType.DOCUMENT_DUPLICATE: "add_document",
    EventType.DOCUMENT_INDEXED: None,  # asynchronous: interleaves unpredictably with the user's steps
    EventType.DOCUMENT_FAILED: None,
    EventType.QUESTION_ASKED: "ask_question",
    EventType.EVIDENCE_RETRIEVED: None,  # part of asking
    EventType.ANSWER_GENERATED: "read_answer",
    EventType.ANSWER_INSUFFICIENT: "read_answer",
    EventType.ANSWER_UNAVAILABLE: None,
}

# Attribute values are small scalars only; this keeps text out of the stream by construction.
Scalar = str | int | float | bool | None


class WorkflowEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(pattern=_EVENT_ID.pattern)
    workspace_id: str
    event_type: EventType
    occurred_at: str  # ISO 8601 UTC, sortable as a string
    attributes: dict[str, Scalar] = Field(default_factory=dict)


def new_event_id() -> str:
    return f"evt_{secrets.token_urlsafe(16)}"


def step_of(event: WorkflowEvent) -> str | None:
    return NORMALIZED[event.event_type]
