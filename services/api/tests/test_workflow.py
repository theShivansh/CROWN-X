"""Workflow Learning Lite (ADR-018, FR-WL-01 to 05): native events, a deterministic miner, suggestions
with defined scores and linked events. Suggest only: nothing is automated."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from crownx.domain.events import EventType, WorkflowEvent, new_event_id
from crownx.domain.workflow import DEFINITIONS, MinerConfig, mine

WS = "ws_AAAAAAAAAAAAAAAAAAAAAA"
START = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)
ADD, ASK, READ = (
    EventType.DOCUMENT_UPLOADED,
    EventType.QUESTION_ASKED,
    EventType.ANSWER_GENERATED,
)


def events(*sessions: list[EventType], gap_minutes: int = 120) -> list[WorkflowEvent]:
    """Each session's events a minute apart; sessions start `gap_minutes` apart. IDs are
    deterministic."""
    out = []
    n = 0
    for s, session in enumerate(sessions):
        for i, event_type in enumerate(session):
            n += 1
            at = START + timedelta(minutes=s * gap_minutes + i)
            out.append(
                WorkflowEvent(
                    event_id=f"evt_{n:022d}",
                    workspace_id=WS,
                    event_type=event_type,
                    occurred_at=at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                )
            )
    return out


# ---------------------------------------------------------------- events


def test_events_carry_scalars_only_so_no_text_can_enter_the_stream():
    with pytest.raises(ValidationError):
        WorkflowEvent(
            event_id=new_event_id(),
            workspace_id=WS,
            event_type=ASK,
            occurred_at="2026-09-18T09:00:00.000000Z",
            attributes={"question": {"text": "nested"}},
        )
    with pytest.raises(ValidationError):
        WorkflowEvent(event_id="bad", workspace_id=WS, event_type=ASK, occurred_at="x")


# ---------------------------------------------------------------- the miner


def test_a_repeated_sequence_is_found_with_the_right_support_and_scores():
    stream = events([ADD, ASK, READ], [ADD, ASK, READ], [ADD, ASK, READ])
    [suggestion] = mine(stream)
    assert suggestion.steps == ["add_document", "ask_question", "read_answer"]
    assert suggestion.name == "Add a document → Ask a question → Read the answer"
    assert suggestion.support == 3
    assert suggestion.confidence == 1.0
    assert suggestion.recency == stream[-1].occurred_at
    assert len(suggestion.traces) == 3


def test_a_one_off_sequence_is_ignored():
    assert mine(events([ADD, ASK, READ], [ASK, READ, ADD])) == []


def test_below_minimum_support_is_ignored_and_the_threshold_is_configurable():
    stream = events([ADD, ASK, READ], [ADD, ASK, READ])
    assert mine(stream) == []
    assert mine(stream, MinerConfig(min_support=2))[0].support == 2


def test_reordered_near_misses_do_not_count_toward_each_other():
    stream = events([ADD, ASK, READ], [ASK, ADD, READ], [ADD, READ, ASK], [ADD, ASK, READ])
    assert mine(stream) == []  # the exact order occurs only twice


def test_duplicate_events_do_not_inflate_support():
    stream = events([ADD, ASK, READ], [ADD, ASK, READ], [ADD, ASK, READ])
    assert mine(stream + stream)[0].support == 3


def test_consecutive_repeats_collapse_into_one_step():
    stream = events([ADD, ADD, ADD, ASK, READ], [ADD, ASK, READ], [ADD, ADD, ASK, READ])
    [suggestion] = mine(stream)
    assert suggestion.steps == ["add_document", "ask_question", "read_answer"]
    assert suggestion.support == 3
    assert len(suggestion.traces[0]) == 5  # the three uploads plus the question and the answer


def test_a_gap_over_thirty_minutes_starts_a_new_session():
    # ADD ASK, then READ in a separate burst, three times over.
    bursts = [[ADD, ASK], [READ]] * 3
    # Bursts 40 minutes apart: every burst is its own session, so no sequence spans them.
    assert mine(events(*bursts, gap_minutes=40)) == []
    # Bursts 10 minutes apart: one session, and the three rounds form the workflow.
    assert mine(events(*bursts, gap_minutes=10))[0].support == 3


def test_interleaved_unrelated_steps_break_a_contiguous_sequence():
    stream = events([ADD, ASK, READ], [ADD, ADD, ASK, READ], [ADD, ASK, ASK, READ, READ])
    # Repeats collapse, so all three sessions are ADD ASK READ.
    assert mine(stream)[0].support == 3
    broken = events([ADD, ASK, READ], [ADD, READ, ASK, READ], [ADD, ASK, READ])
    assert mine(broken) == []


def test_a_sub_sequence_with_the_same_support_is_not_suggested_twice():
    stream = events(*[[ADD, ASK, READ, ASK, READ]] * 3)
    suggestions = mine(stream)
    steps = [tuple(s.steps) for s in suggestions]
    assert ("add_document", "ask_question", "read_answer", "ask_question", "read_answer") in steps
    assert ("add_document", "ask_question", "read_answer") not in steps


def test_confidence_is_support_over_the_first_steps_occurrences():
    stream = events([ADD, ASK, READ], [ADD, ASK, READ], [ADD, ASK, READ], [ADD, READ, ASK])
    [suggestion] = mine(stream)
    assert suggestion.confidence == pytest.approx(3 / 4)
    assert 0 <= suggestion.confidence <= 1


def test_steps_without_workflow_meaning_are_left_out():
    noise = [EventType.DOCUMENT_UPLOAD_REQUESTED, EventType.DOCUMENT_INDEXED]
    stream = events(*[[ADD, *noise, ASK, EventType.EVIDENCE_RETRIEVED, READ]] * 3)
    [suggestion] = mine(stream)
    assert suggestion.steps == ["add_document", "ask_question", "read_answer"]


def test_every_suggestion_links_to_concrete_events_in_order():
    stream = events(*[[ADD, ASK, READ]] * 4)
    by_id = {e.event_id: e for e in stream}
    for suggestion in mine(stream):
        for trace in suggestion.traces:
            assert all(event_id in by_id for event_id in trace)
            assert trace == sorted(trace, key=lambda i: by_id[i].occurred_at)


def test_identical_input_gives_byte_identical_output_whatever_the_order():
    stream = events(*[[ADD, ASK, READ, ASK, READ]] * 3, [ADD, ASK, READ])
    first = json.dumps([s.model_dump() for s in mine(stream)], sort_keys=True)
    second = json.dumps([s.model_dump() for s in mine(list(reversed(stream)))], sort_keys=True)
    assert first == second


def test_every_score_is_defined():
    assert {"support", "recency", "confidence"} <= set(DEFINITIONS)


# ---------------------------------------------------------------- end to end through the API

BRIEF = b"# Brief\n\nFinal submissions close on 20 September 2026.\n"


def test_upload_and_questions_write_events_and_a_suggestion_appears(api):
    ws = api.new_workspace()
    for n in range(3):
        api.upload(ws, f"brief-{n}.md", BRIEF + str(n).encode())
        _, body, _ = api.call(
            "POST", f"/workspaces/{ws}/query", {"question": "When do they close?"}
        )
        status, _, _ = api.call("POST", f"/workspaces/{ws}/queries/{body['query_id']}/answer")
        assert status == 200

    types = api.store.event_types(ws)
    assert types[:6] == [
        "document_upload_requested",
        "document_uploaded",
        "document_indexed",
        "question_asked",
        "evidence_retrieved",
        "answer_generated",
    ]
    for event in api.store.list_events(ws):
        assert all(not isinstance(v, str) or len(v) < 64 for v in event.attributes.values())
        assert "When do they close?" not in event.model_dump_json()

    status, body, _ = api.call("GET", f"/workspaces/{ws}/workflow-suggestions")
    assert status == 200, body
    assert body["automation"] == "none"
    assert set(body["definitions"]) >= {"support", "recency", "confidence"}
    # All three rounds land in one session, so the whole round repeats as one pattern.
    top = body["suggestions"][0]
    assert top["steps"][:3] == ["add_document", "ask_question", "read_answer"]
    assert top["support"] >= 1


def test_duplicate_uploads_and_insufficient_answers_are_recorded(api):
    ws = api.new_workspace()
    api.upload(ws, "brief.md", BRIEF)
    api.upload(ws, "copy.md", BRIEF, ingest=False)
    empty = api.new_workspace()
    _, body, _ = api.call("POST", f"/workspaces/{empty}/query", {"question": "Anything?"})
    api.call("POST", f"/workspaces/{empty}/queries/{body['query_id']}/answer")

    assert "document_duplicate" in api.store.event_types(ws)
    assert api.store.event_types(empty) == [
        "question_asked",
        "evidence_retrieved",
        "answer_insufficient",
    ]


def test_suggestions_are_scoped_to_their_workspace(api):
    ws, other = api.new_workspace(), api.new_workspace()
    api.upload(ws, "brief.md", BRIEF)
    _, body, _ = api.call("GET", f"/workspaces/{other}/workflow-suggestions")
    assert body["suggestions"] == []
    assert all(e.workspace_id == ws for e in api.store.list_events(ws))
    status, _, _ = api.call("GET", "/workspaces/ws_BBBBBBBBBBBBBBBBBBBBBB/workflow-suggestions")
    assert status == 404


def test_a_failing_event_store_never_fails_the_request(api):
    ws = api.new_workspace()
    api.store.event_error = ConnectionError("events table unreachable")
    api.upload(ws, "brief.md", BRIEF)
    status, body, _ = api.call("POST", f"/workspaces/{ws}/query", {"question": "When?"})
    assert status == 200 and body["query_id"]
