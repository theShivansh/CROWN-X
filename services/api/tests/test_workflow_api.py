"""Workflow Learning Lite through the API (M5, ADR-022): the flag, client events, refresh and naming,
save and dismiss. Suggestions only: nothing here runs a workflow."""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from crownx.adapters.groq import GroqAnswerer, name_workflow
from crownx.adapters.groq_mock import MockGroqTransport

BRIEF = b"# Brief\n\nFinal submissions close on 20 September 2026.\n"


def uuid7() -> str:
    ms = int(time.time() * 1000)
    rand = secrets.randbits(74)
    value = (
        (ms << 80) | (0x7 << 76) | ((rand >> 62) << 64) | (0b10 << 62) | (rand & ((1 << 62) - 1))
    )
    return str(uuid.UUID(int=value))


def client_event(
    api, ws: str, event_type: str, event_id: str | None = None, at: str | None = None, **ref
):
    """A browser event, stamped with the browser's own clock."""
    body = {
        "event_id": event_id or uuid7(),
        "event_type": event_type,
        "occurred_at": at or datetime.now(UTC).isoformat(),
        "ref": ref,
    }
    return api.call("POST", f"/workspaces/{ws}/events", body), body


def sprint_review(api, ws: str) -> None:
    """The demo routine: ask, then inspect the conflict, open the timeline, copy the answer."""
    _, query, _ = api.call(
        "POST", f"/workspaces/{ws}/query", {"question": "When do submissions close?"}
    )
    api.call("POST", f"/workspaces/{ws}/queries/{query['query_id']}/answer")
    for event_type in ("conflict_opened", "timeline_opened", "answer_copied"):
        (status, body, _), _ = client_event(api, ws, event_type, query_id=query["query_id"])
        assert status == 201, body


def workspace_with_routine(api, times: int = 3) -> str:
    ws = api.new_workspace()
    api.upload(ws, "brief.md", BRIEF)
    for _ in range(times):
        sprint_review(api, ws)
    return ws


ROUTINE = ["ask_question", "read_answer", "inspect_conflict", "open_timeline", "copy_answer"]


# Flag -------------------------------------------------------------------------------------------


def test_with_the_flag_off_every_workflow_route_is_a_404_and_nothing_is_written(api):
    ws = workspace_with_routine(api)
    events_before = len(api.store.events)
    api.service.workflows.enabled = False
    routes = [
        ("POST", f"/workspaces/{ws}/events"),
        ("GET", f"/workspaces/{ws}/workflow-suggestions"),
        ("POST", f"/workspaces/{ws}/workflow-suggestions/refresh"),
        ("POST", f"/workspaces/{ws}/workflow-suggestions/wf_x/save"),
        ("POST", f"/workspaces/{ws}/workflow-suggestions/wf_x/dismiss"),
    ]
    for method, path in routes:
        status, body, _ = api.call(
            method, path, {"event_id": uuid7(), "event_type": "answer_copied"}
        )
        assert status == 404 and body["error"]["code"] == "not_found", (method, path)
    assert len(api.store.events) == events_before


# Events -----------------------------------------------------------------------------------------


def test_a_retried_client_event_is_stored_once(api):
    ws = api.new_workspace()
    event_id, at = uuid7(), datetime.now(UTC).isoformat()
    for _ in range(3):
        (status, body, _), _ = client_event(api, ws, "evidence_opened", event_id=event_id, at=at)
        assert status == 201 and body["event_id"] == event_id
    assert [e.event_id for e in api.store.list_events(ws)] == [event_id]


@pytest.mark.parametrize(
    "event_type", ["question_asked", "document_uploaded", "workflow_saved", "made_up"]
)
def test_server_owned_and_unknown_types_are_refused_from_the_client(api, event_type):
    ws = api.new_workspace()
    (status, body, _), _ = client_event(api, ws, event_type)
    assert status == 400 and "event_type" in body["error"]["message"]
    assert api.store.list_events(ws) == []


def test_an_event_carries_ids_only(api):
    ws = api.new_workspace()
    (status, _, _), _ = client_event(api, ws, "answer_copied", query_id="The deadline is 22 Sept!")
    assert status == 400
    (status, _, _), _ = client_event(api, ws, "answer_copied", answer="22 September")
    assert status == 400
    status, _, _ = api.call(
        "POST",
        f"/workspaces/{ws}/events",
        {
            "event_id": "not-a-uuid",
            "event_type": "answer_copied",
            "occurred_at": datetime.now(UTC).isoformat(),
        },
    )
    assert status == 400


def test_events_are_ordered_by_the_server_clock_whatever_the_browser_says(api):
    """A browser clock hours behind can't move a step before the answer it followed."""
    ws = api.new_workspace()
    api.upload(ws, "brief.md", BRIEF)
    _, query, _ = api.call(
        "POST", f"/workspaces/{ws}/query", {"question": "When do submissions close?"}
    )
    api.call("POST", f"/workspaces/{ws}/queries/{query['query_id']}/answer")
    early = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    (status, _, _), _ = client_event(api, ws, "answer_copied", at=early)
    assert status == 201
    events = api.store.list_events(ws)
    assert events[-1].event_type.value == "answer_copied"
    assert events[-1].attributes["client_at"].startswith(early[:13])


def test_client_events_have_an_hourly_limit(api):
    ws = api.new_workspace()
    api.service.workflows._events_per_hour = 2
    assert client_event(api, ws, "answer_copied")[0][0] == 201
    assert client_event(api, ws, "answer_copied")[0][0] == 201
    (status, body, _), _ = client_event(api, ws, "answer_copied")
    assert status == 429 and body["error"]["code"] == "limit_reached"


def test_events_and_suggestions_never_cross_workspaces(api):
    a = workspace_with_routine(api)
    b = api.new_workspace()
    _, body, _ = api.call("GET", f"/workspaces/{b}/workflow-suggestions")
    assert body["suggestions"] == []
    _, mine, _ = api.call("GET", f"/workspaces/{a}/workflow-suggestions")
    sid = mine["suggestions"][0]["suggestion_id"]
    for path in (
        f"/workspaces/{b}/workflow-suggestions/{sid}/save",
        f"/workspaces/{b}/workflow-suggestions/{sid}/dismiss",
    ):
        status, body, _ = api.call("POST", path)
        assert status == 404
    status, _, _ = api.call("GET", "/workspaces/ws_BBBBBBBBBBBBBBBBBBBBBB/workflow-suggestions")
    assert status == 404


# Suggestions ------------------------------------------------------------------------------------


def test_the_routine_three_times_is_one_suggestion_with_its_traces(api):
    ws = workspace_with_routine(api)
    status, body, _ = api.call("GET", f"/workspaces/{ws}/workflow-suggestions")
    assert status == 200 and body["automation"] == "none"
    [top] = [s for s in body["suggestions"] if s["steps"] == ROUTINE]
    assert top["support"] == 3
    assert top["first_step_count"] == 3 and top["confidence"] == 1.0
    assert len(top["traces"]) == 3 and all(len(t) == len(ROUTINE) for t in top["traces"])
    assert len(top["trace_times"]) == 3 and len(top["trace_sessions"]) == 3
    assert top["example_session_ids"] == [top["trace_sessions"][0]]  # one session, three times
    stored = {e.event_id for e in api.store.list_events(ws)}
    assert {eid for trace in top["traces"] for eid in trace} <= stored
    assert top["named_by"] == "rule" and top["name"] == top["rule_name"]
    assert set(body["definitions"]) >= {"support", "confidence", "recency", "session"}


def test_refresh_names_a_new_suggestion_once_from_step_types_only(api):
    ws = workspace_with_routine(api)
    calls = []

    def namer(steps, examples):
        calls.append((steps, examples))
        return (
            "Prepare sprint review",
            "Check the deadline conflict and share the answer.",
            "test-model",
        )

    api.service.workflows._namer = namer
    for _ in range(2):
        status, body, _ = api.call("POST", f"/workspaces/{ws}/workflow-suggestions/refresh")
        assert status == 200
    [top] = [s for s in body["suggestions"] if s["steps"] == ROUTINE]
    assert top["name"] == "Prepare sprint review" and top["named_by"] == "test-model"
    assert len([c for c in calls if c[0] == ROUTINE]) == 1  # never asked twice
    steps, examples = next(c for c in calls if c[0] == ROUTINE)
    assert examples and all(e[0].endswith("+0s") for e in examples)
    assert "evt_" not in str(examples) and "Brief" not in str(examples)  # types and times only


def test_a_failed_naming_call_keeps_the_rule_name(api):
    ws = workspace_with_routine(api)

    def broken(steps, examples):
        raise RuntimeError("model down")

    api.service.workflows._namer = broken
    status, body, _ = api.call("POST", f"/workspaces/{ws}/workflow-suggestions/refresh")
    assert status == 200
    [top] = [s for s in body["suggestions"] if s["steps"] == ROUTINE]
    assert top["named_by"] == "rule" and top["name"] == top["rule_name"]


def test_save_writes_immutable_versions_and_records_the_save(api):
    ws = workspace_with_routine(api)
    _, body, _ = api.call("GET", f"/workspaces/{ws}/workflow-suggestions")
    sid = next(s["suggestion_id"] for s in body["suggestions"] if s["steps"] == ROUTINE)

    status, first, _ = api.call("POST", f"/workspaces/{ws}/workflow-suggestions/{sid}/save")
    assert status == 201 and first["template"]["version"] == 1
    status, second, _ = api.call(
        "POST", f"/workspaces/{ws}/workflow-suggestions/{sid}/save", {"name": "Sprint review prep"}
    )
    assert status == 201 and second["template"]["version"] == 2
    assert second["template"]["name"] == "Sprint review prep"
    assert second["template"]["steps"] == ROUTINE and second["template"]["automation"] == "none"

    _, body, _ = api.call("GET", f"/workspaces/{ws}/workflow-suggestions")
    [top] = [s for s in body["suggestions"] if s["suggestion_id"] == sid]
    assert [v["version"] for v in top["saved_versions"]] == [1, 2]
    assert api.store.event_types(ws).count("workflow_saved") == 2
    # Saving isn't a step: the routine's support is unchanged.
    assert top["support"] == 3

    status, body, _ = api.call(
        "POST", f"/workspaces/{ws}/workflow-suggestions/{sid}/save", {"name": "<b>"}
    )
    assert status == 400


def test_dismiss_hides_a_suggestion_until_it_happens_again(api):
    ws = workspace_with_routine(api)
    _, body, _ = api.call("GET", f"/workspaces/{ws}/workflow-suggestions")
    sid = next(s["suggestion_id"] for s in body["suggestions"] if s["steps"] == ROUTINE)

    status, _, _ = api.call("POST", f"/workspaces/{ws}/workflow-suggestions/{sid}/dismiss")
    assert status == 200
    _, body, _ = api.call("GET", f"/workspaces/{ws}/workflow-suggestions")
    assert sid not in {s["suggestion_id"] for s in body["suggestions"]}

    sprint_review(api, ws)  # a fourth time: support grows past what was dismissed
    _, body, _ = api.call("GET", f"/workspaces/{ws}/workflow-suggestions")
    [top] = [s for s in body["suggestions"] if s["suggestion_id"] == sid]
    assert top["support"] == 4

    status, _, _ = api.call("POST", f"/workspaces/{ws}/workflow-suggestions/wf_unknown/dismiss")
    assert status == 404


# Naming over Groq's transport ---------------------------------------------------------------------


def test_groq_names_a_workflow_through_the_tool_and_falls_back_on_failure():
    transport = MockGroqTransport()
    answerer = GroqAnswerer(
        "k", "openai/gpt-oss-120b", transport=transport, fallback_model_id="openai/gpt-oss-20b"
    )
    named = name_workflow(answerer, ROUTINE, [["ask_question +0s", "read_answer +4s"]])
    assert named is not None
    name, model = named
    assert model == "openai/gpt-oss-120b" and 3 <= len(name.name) <= 40
    request = transport.calls[-1]
    assert request["tool_choice"]["function"]["name"] == "name_workflow"
    assert "evt_" not in str(request["messages"])

    def failing(url, headers, body, timeout):
        raise TimeoutError("down")

    down = GroqAnswerer(
        "k", "openai/gpt-oss-120b", transport=failing, fallback_model_id="openai/gpt-oss-20b"
    )
    assert name_workflow(down, ROUTINE, []) is None

    def bad_name(url, headers, body, timeout):
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "name_workflow",
                                    "arguments": '{"name": "<script>", "description": "x y z"}',
                                }
                            }
                        ]
                    }
                }
            ]
        }

    assert name_workflow(GroqAnswerer("k", "m", transport=bad_name), ROUTINE, []) is None
