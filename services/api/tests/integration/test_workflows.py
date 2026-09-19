"""Workflow Learning Lite end to end on the deployed stack (M5): events, refresh, a suggestion with its
traces, save (two versions), dismiss, a retried event and another workspace. Needs WorkflowsEnabled.

    EVAL_API_URL=https://<api-id>.execute-api.ap-south-1.amazonaws.com uv run pytest tests/integration -q -k workflow

A throwaway workspace; no document and no answer model: the routine is built from questions that
find no evidence (the server still records `question_asked` and `answer_insufficient`) and UI events.
At most one naming call reaches Groq, on the refresh.
"""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import UTC, datetime

import pytest

from integration.test_security_acceptance import call, new_workspace, ok

pytestmark = pytest.mark.integration

ROUTINE = ["ask_question", "read_answer", "inspect_conflict", "open_timeline", "copy_answer"]


def uuid7() -> str:
    ms = int(time.time() * 1000)
    rand = secrets.randbits(74)
    value = (
        (ms << 80) | (0x7 << 76) | ((rand >> 62) << 64) | (0b10 << 62) | (rand & ((1 << 62) - 1))
    )
    return str(uuid.UUID(int=value))


def event(ws: str, event_type: str, event_id: str | None = None) -> tuple[int, dict]:
    return call(
        "POST",
        f"/workspaces/{ws}/events",
        {
            "event_id": event_id or uuid7(),
            "event_type": event_type,
            "occurred_at": datetime.now(UTC).isoformat(),
        },
    )


def routine(ws: str) -> None:
    query = ok("POST", f"/workspaces/{ws}/query", {"question": "What is the review date?"})
    ok(
        "POST", f"/workspaces/{ws}/queries/{query['query_id']}/answer"
    )  # insufficient: no model call
    for event_type in ("conflict_opened", "timeline_opened", "answer_copied"):
        status, body = event(ws, event_type)
        assert status == 201, body


def test_events_refresh_suggestion_save_and_dismiss_on_the_deployed_stack():
    ws = new_workspace()
    for _ in range(3):
        routine(ws)

    # A retried event is recorded once.
    retried = uuid7()
    for _ in range(2):
        status, body = event(ws, "evidence_opened", retried)
        assert status == 201 and body["event_id"] == retried

    status, view = call("POST", f"/workspaces/{ws}/workflow-suggestions/refresh")
    assert status == 200 and view["automation"] == "none"
    [top] = [s for s in view["suggestions"] if s["steps"] == ROUTINE]
    assert top["support"] == 3 and len(top["traces"]) == 3
    assert top["named_by"] in ("rule", "openai/gpt-oss-120b", "openai/gpt-oss-20b")
    assert 3 <= len(top["name"]) <= 120
    sid = top["suggestion_id"]

    status, first = call("POST", f"/workspaces/{ws}/workflow-suggestions/{sid}/save")
    assert status == 201 and first["template"]["version"] == 1
    status, second = call(
        "POST", f"/workspaces/{ws}/workflow-suggestions/{sid}/save", {"name": "Review prep"}
    )
    assert status == 201 and second["template"]["version"] == 2

    view = ok("GET", f"/workspaces/{ws}/workflow-suggestions")
    [top] = [s for s in view["suggestions"] if s["suggestion_id"] == sid]
    assert [v["version"] for v in top["saved_versions"]] == [1, 2]
    assert top["support"] == 3  # saving isn't a step

    other = new_workspace()
    status, _ = call("POST", f"/workspaces/{other}/workflow-suggestions/{sid}/save")
    assert status == 404
    assert ok("GET", f"/workspaces/{other}/workflow-suggestions")["suggestions"] == []

    status, _ = call("POST", f"/workspaces/{ws}/workflow-suggestions/{sid}/dismiss")
    assert status == 200
    view = ok("GET", f"/workspaces/{ws}/workflow-suggestions")
    assert sid not in {s["suggestion_id"] for s in view["suggestions"]}
