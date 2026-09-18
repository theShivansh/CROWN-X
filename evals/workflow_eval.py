"""Workflow Learning Lite benchmark (docs/EVALUATION.md §6, ADR-018). Synthetic event traces with
known answers: repeated true workflows, near-miss reorderings, duplicates, unrelated interleavings and
one-off sequences. Deterministic: a fixed seed, no clock, no model.

    cd services/api && uv run python ../../evals/workflow_eval.py

Metrics: pattern precision and recall against the planted workflows, false-suggestion count,
support-count accuracy, and determinism (identical output for the same input, in any order).
"""

from __future__ import annotations

import json
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api" / "src"))

from crownx.domain.events import EventType, WorkflowEvent  # noqa: E402
from crownx.domain.workflow import mine  # noqa: E402

ADD, ASK, READ = EventType.DOCUMENT_UPLOADED, EventType.QUESTION_ASKED, EventType.ANSWER_GENERATED
INSUFFICIENT = EventType.ANSWER_INSUFFICIENT
DUPLICATE = EventType.DOCUMENT_DUPLICATE
NOISE = [
    EventType.DOCUMENT_UPLOAD_REQUESTED,
    EventType.DOCUMENT_INDEXED,
    EventType.EVIDENCE_RETRIEVED,
]
START = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)


def scenario(seed: int) -> tuple[list[WorkflowEvent], dict[tuple[str, ...], int]]:
    """One workspace's stream and the workflows planted in it, with their true support."""
    rng = random.Random(seed)
    sessions: list[list[EventType]] = []
    planted: dict[tuple[str, ...], int] = {}

    # A true workflow: upload, ask, read, ask again, read again. 3 to 5 sessions.
    true_count = rng.randint(3, 5)
    sessions += [[ADD, ASK, READ, ASK, INSUFFICIENT] for _ in range(true_count)]
    planted[("add_document", "ask_question", "read_answer", "ask_question", "read_answer")] = (
        true_count
    )
    # Near misses: the same steps reordered, twice (below the support minimum).
    sessions += [[ASK, ADD, READ, ASK, READ], [ADD, READ, ASK, READ, ASK]]
    # One-off sequences.
    sessions += [[ASK, READ], [ADD, DUPLICATE, ASK]]
    rng.shuffle(sessions)

    events: list[WorkflowEvent] = []
    n = 0
    for s, session in enumerate(sessions):
        minute = 0
        for event_type in session:
            # Unrelated interleavings: system events that carry no workflow step.
            for noise in rng.sample(NOISE, rng.randint(0, 2)):
                n += 1
                minute += 1
                events.append(_event(seed, n, noise, s, minute))
            n += 1
            minute += 1
            events.append(_event(seed, n, event_type, s, minute))
    # Exact duplicates of a few events (a retried write): must not inflate support.
    events += rng.sample(events, 5)
    return events, planted


def _event(seed: int, n: int, event_type: EventType, session: int, minute: int) -> WorkflowEvent:
    at = START + timedelta(hours=2 * session, minutes=minute)
    return WorkflowEvent(
        event_id=f"evt_{seed:06d}{n:016d}",
        workspace_id="ws_WorkflowBenchmark00000",
        event_type=event_type,
        occurred_at=at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    )


def main(seeds: int = 20) -> dict:
    true_positive = false_positive = false_negative = support_exact = 0
    deterministic = True
    for seed in range(seeds):
        events, planted = scenario(seed)
        found = {tuple(s.steps): s for s in mine(events)}
        again = mine(list(reversed(events)))
        deterministic &= [s.model_dump() for s in found.values()] == [s.model_dump() for s in again]
        for steps, support in planted.items():
            if steps in found:
                true_positive += 1
                support_exact += found[steps].support == support
            else:
                false_negative += 1
        false_positive += sum(1 for steps in found if steps not in planted)
    report = {
        "scenarios": seeds,
        "pattern_precision": round(true_positive / max(1, true_positive + false_positive), 4),
        "pattern_recall": round(true_positive / max(1, true_positive + false_negative), 4),
        "false_suggestions": false_positive,
        "support_count_accuracy": round(support_exact / max(1, true_positive), 4),
        "deterministic": deterministic,
    }
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    result = main()
    ok = result["deterministic"] and result["pattern_recall"] == 1.0
    sys.exit(0 if ok else 1)
