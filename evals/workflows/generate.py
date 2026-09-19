"""Labelled synthetic event traces for the Workflow Learning Lite benchmark (docs/EVALUATION.md §6,
ADR-018, ADR-022). A fixed seed, no clock, no model: the same seed always gives the same streams.

Each scenario is one workspace's event stream with two planted workflows and everything that should
not become one:
- true repeated workflows:
  - "sprint review": ask, read, inspect the conflict, open the timeline, copy the answer;
  - "intake": add a document, ask, read, open a cited passage;
  - one of them sometimes happens twice in one session (support counts both);
- near misses: the sprint review with two steps swapped, or with a step missing (each below the
  support minimum on its own);
- interleavings: system events with no workflow step between steps (they must not break a run), and
  one sprint review with an extra step in the middle (it must not count: runs are contiguous);
- duplicates: double-clicks (the same step twice in a row) and retried writes (the same event ID);
- one-off sequences.

The label is each planted workflow's true support: its contiguous, non-overlapping occurrences.
"""

from __future__ import annotations

import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api" / "src"))

from crownx.domain.events import EventType as E  # noqa: E402
from crownx.domain.events import WorkflowEvent  # noqa: E402

START = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)
NOISE = [E.DOCUMENT_UPLOAD_REQUESTED, E.DOCUMENT_INDEXED, E.EVIDENCE_RETRIEVED]

SPRINT_REVIEW = [
    E.QUESTION_ASKED,
    E.ANSWER_GENERATED,
    E.CONFLICT_OPENED,
    E.TIMELINE_OPENED,
    E.ANSWER_COPIED,
]
INTAKE = [E.DOCUMENT_UPLOADED, E.QUESTION_ASKED, E.ANSWER_GENERATED, E.EVIDENCE_OPENED]
STEPS = {
    "sprint_review": (
        "ask_question",
        "read_answer",
        "inspect_conflict",
        "open_timeline",
        "copy_answer",
    ),
    "intake": ("add_document", "ask_question", "read_answer", "open_evidence"),
}


def scenario(seed: int) -> tuple[list[WorkflowEvent], dict[tuple[str, ...], int]]:
    rng = random.Random(seed)
    sessions: list[list[E]] = []
    labels: dict[tuple[str, ...], int] = {}

    review = rng.randint(3, 5)
    sessions += [list(SPRINT_REVIEW) for _ in range(review)]
    if rng.random() < 0.5:  # twice in one session: two occurrences
        sessions.append(SPRINT_REVIEW + SPRINT_REVIEW)
        review += 2
    labels[STEPS["sprint_review"]] = review

    intake = rng.randint(3, 4)
    sessions += [list(INTAKE) for _ in range(intake)]
    labels[STEPS["intake"]] = intake

    # Near misses, each below the minimum support on its own.
    swapped = [
        E.QUESTION_ASKED,
        E.ANSWER_GENERATED,
        E.TIMELINE_OPENED,
        E.CONFLICT_OPENED,
        E.ANSWER_COPIED,
    ]
    missing = [E.QUESTION_ASKED, E.ANSWER_GENERATED, E.CONFLICT_OPENED, E.ANSWER_COPIED]
    sessions += [swapped, swapped, missing, missing]
    # An interrupted sprint review: an extra step in the middle, so it isn't a contiguous run.
    sessions.append(
        [
            E.QUESTION_ASKED,
            E.ANSWER_GENERATED,
            E.EVIDENCE_OPENED,
            E.CONFLICT_OPENED,
            E.TIMELINE_OPENED,
            E.ANSWER_COPIED,
        ]
    )
    # One-offs.
    sessions += [
        [E.QUESTION_ASKED, E.ANSWER_GENERATED],
        [E.DOCUMENT_UPLOADED, E.DOCUMENT_DUPLICATE, E.QUESTION_ASKED],
    ]
    rng.shuffle(sessions)

    events: list[WorkflowEvent] = []
    n = 0
    for s, session in enumerate(sessions):
        second = 0
        for event_type in session:
            for noise in rng.sample(NOISE, rng.randint(0, 2)):  # steps-free system events
                n, second = n + 1, second + 7
                events.append(_event(seed, n, noise, s, second))
            repeats = 2 if rng.random() < 0.15 else 1  # a double-click: the same step twice
            for _ in range(repeats):
                n, second = n + 1, second + 7
                events.append(_event(seed, n, event_type, s, second))
    events += rng.sample(events, 5)  # retried writes: identical event IDs
    return events, labels


def _event(seed: int, n: int, event_type: E, session: int, second: int) -> WorkflowEvent:
    at = START + timedelta(hours=2 * session, seconds=second)  # sessions two hours apart
    return WorkflowEvent(
        event_id=f"evt_{seed:06d}{n:016d}",
        workspace_id="ws_WorkflowBenchmark00000",
        event_type=event_type,
        occurred_at=at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    )
