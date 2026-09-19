"""Workflow Learning Lite miner (FR-WL-03 to 05; ADR-005, ADR-018). Pure and deterministic: no model,
no clock, no randomness, so identical events and config always give identical suggestions.

1. Deduplicate events by `event_id` and order them by (`occurred_at`, `event_id`).
2. Normalize each to a step (domain/events.py); events without a step are dropped.
3. Split into sessions: a gap over `session_gap_minutes` starts a new one.
4. Collapse consecutive repeats of a step into one ("added 6 documents" is one step).
5. Count contiguous ordered step sequences of length `min_length`..`max_length`, non-overlapping
   within a session, scanning left to right.
6. Keep sequences with support >= `min_support` and at least `min_distinct_steps` different steps
   (going back and forth between asking and reading is usage, not a workflow), that aren't part of a
   longer kept sequence with the same support (so "a b c" isn't also suggested as "a b").

Suggestions only: nothing here executes or automates a workflow.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from crownx.domain.events import WorkflowEvent, step_of

DEFINITIONS = {
    "support": "How many times the whole sequence occurred, counted without overlap within a session.",
    "recency": "When the sequence last finished (UTC).",
    "confidence": (
        "support divided by how many times the sequence's first step occurred: the share of times "
        "that starting this sequence led to finishing it. Between 0 and 1."
    ),
    "session": (
        "Events with no gap longer than 30 minutes between them. A session's ID is derived from its "
        "first event, so the same events always give the same sessions."
    ),
}

STEP_LABELS = {
    "add_document": "Add a document",
    "ask_question": "Ask a question",
    "read_answer": "Read the answer",
    "open_evidence": "Open a cited passage",
    "inspect_conflict": "Inspect a conflict",
    "open_timeline": "Open the timeline",
    "copy_answer": "Copy the answer",
}


@dataclass(frozen=True)
class MinerConfig:
    session_gap_minutes: int = 30
    min_length: int = 3
    max_length: int = 7
    min_support: int = 3
    min_distinct_steps: int = 3
    max_traces: int = 5


class WorkflowSuggestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    suggestion_id: str
    name: str
    steps: list[str]
    support: int
    recency: str
    confidence: float
    traces: list[list[str]]  # event IDs of each representative occurrence, oldest first
    trace_sessions: list[str]  # the session of each trace, in the same order
    trace_times: list[list[str]]  # when each step of each trace happened (UTC), in the same order
    example_session_ids: list[str]  # up to three distinct sessions where it occurred, newest first
    first_step_count: int  # the confidence's denominator, so the UI can say it in words


@dataclass
class _Step:
    step: str
    session_id: str
    first_at: str
    event_ids: list[str] = field(default_factory=list)
    last_at: str = ""


def mine(
    events: list[WorkflowEvent], config: MinerConfig | None = None
) -> list[WorkflowSuggestion]:
    config = config or MinerConfig()
    sessions = _sessions(events, config.session_gap_minutes)

    first_step_counts: dict[str, int] = {}
    for session in sessions:
        for step in session:
            first_step_counts[step.step] = first_step_counts.get(step.step, 0) + 1

    occurrences: dict[tuple[str, ...], list[list[_Step]]] = {}
    for length in range(config.min_length, config.max_length + 1):
        for session in sessions:
            position = 0
            taken: dict[tuple[str, ...], int] = {}  # sequence -> first free index in this session
            while position + length <= len(session):
                window = session[position : position + length]
                key = tuple(s.step for s in window)
                if position >= taken.get(key, 0):
                    occurrences.setdefault(key, []).append(window)
                    taken[key] = position + length
                position += 1

    candidates = {
        key: found
        for key, found in occurrences.items()
        if len(found) >= config.min_support and len(set(key)) >= config.min_distinct_steps
    }
    kept = {
        key: found
        for key, found in candidates.items()
        if not any(
            len(other) > len(key) and len(candidates[other]) == len(found) and _contains(other, key)
            for other in candidates
        )
    }

    def sessions_of(found: list[list[_Step]]) -> list[str]:
        newest_first = [window[0].session_id for window in reversed(found)]
        return list(dict.fromkeys(newest_first))[:3]

    suggestions = [
        WorkflowSuggestion(
            suggestion_id="wf_" + hashlib.sha256("|".join(key).encode()).hexdigest()[:16],
            name=" → ".join(STEP_LABELS.get(step, step) for step in key),
            steps=list(key),
            support=len(found),
            recency=max(window[-1].last_at for window in found),
            confidence=round(len(found) / first_step_counts[key[0]], 4),
            traces=[
                [event_id for step in window for event_id in step.event_ids]
                for window in found[-config.max_traces :]
            ],
            trace_sessions=[window[0].session_id for window in found[-config.max_traces :]],
            trace_times=[
                [step.first_at for step in window] for window in found[-config.max_traces :]
            ],
            example_session_ids=sessions_of(found),
            first_step_count=first_step_counts[key[0]],
        )
        for key, found in kept.items()
    ]
    suggestions.sort(key=lambda s: (-s.support, -len(s.steps), s.name, s.suggestion_id))
    return suggestions


def _sessions(events: list[WorkflowEvent], gap_minutes: int) -> list[list[_Step]]:
    unique = {event.event_id: event for event in events}
    ordered = sorted(unique.values(), key=lambda e: (e.occurred_at, e.event_id))
    sessions: list[list[_Step]] = []
    session_id = ""
    previous: datetime | None = None
    for event in ordered:
        step = step_of(event)
        if step is None:
            continue
        at = datetime.fromisoformat(event.occurred_at.replace("Z", "+00:00"))
        if previous is None or (at - previous).total_seconds() > gap_minutes * 60:
            sessions.append([])
            session_id = "ses_" + hashlib.sha256(event.event_id.encode()).hexdigest()[:12]
        previous = at
        current = sessions[-1]
        if current and current[-1].step == step:
            current[-1].event_ids.append(event.event_id)  # a repeat of the same step
            current[-1].last_at = event.occurred_at
        else:
            current.append(
                _Step(step, session_id, event.occurred_at, [event.event_id], event.occurred_at)
            )
    return sessions


def _contains(longer: tuple[str, ...], shorter: tuple[str, ...]) -> bool:
    n = len(shorter)
    return any(longer[i : i + n] == shorter for i in range(len(longer) - n + 1))
