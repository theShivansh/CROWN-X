"""The value timeline (M4, FR-09, UI_UX §3.6): one event per source, ordered by the same signals the
selection rule uses, with each change and the conflicts it takes part in. Never crosses workspaces."""

from __future__ import annotations

from test_conflicts_api import BRIEF, UPDATE

DECIDED = b"""Date: Friday, 11 September 2026

Deadline confirmed as 22 September 2026.
"""
UNDATED = b"""Notes from the hallway

The submission deadline is 21 September 2026.
"""


def timeline(api, ws: str, key: str = "subject=submission&attribute=deadline"):
    return api.call("GET", f"/workspaces/{ws}/timeline?{key}")


def test_the_deadline_timeline_orders_by_source_date_and_marks_the_change(api):
    ws = api.new_workspace()
    api.upload(ws, "organiser-update-3.txt", UPDATE)  # uploaded first, dated later
    api.upload(ws, "project-brief-v1.md", BRIEF)
    api.upload(ws, "meeting-notes-sync-5.md", DECIDED)

    status, body, _ = timeline(api, ws)

    assert status == 200, body
    assert body["key"] == "submission/deadline" and body["type"] == "date"
    assert body["selection_rule"] == "newest_source_timestamp"
    events = body["events"]
    assert [e["filename"] for e in events] == [
        "project-brief-v1.md",
        "organiser-update-3.txt",
        "meeting-notes-sync-5.md",
    ]
    assert [e["normalized_value"] for e in events] == ["2026-09-20", "2026-09-22", "2026-09-22"]
    assert [e["changed"] for e in events] == [False, True, False]
    assert [e["selected"] for e in events] == [False, False, True]
    assert body["selected_claim_id"] == events[2]["claim_id"]
    assert all(e["dated"] for e in events)
    # The brief conflicts with both later sources; the two later sources agree with each other.
    assert len(events[0]["conflict_ids"]) == 2
    assert len(events[1]["conflict_ids"]) == len(events[2]["conflict_ids"]) == 1
    # The same IDs `/conflicts` returns, so the UI can link the two views.
    _, listed, _ = api.call("GET", f"/workspaces/{ws}/conflicts")
    pair_ids = {p["conflict_id"] for g in listed["conflicts"] for p in g["pairs"]}
    assert set(events[0]["conflict_ids"]) == pair_ids
    assert "ignore" not in str(body).lower()


def test_an_undated_source_sits_at_its_upload_position_and_says_so(api):
    ws = api.new_workspace()
    api.upload(ws, "project-brief-v1.md", BRIEF)
    api.upload(ws, "hallway.txt", UNDATED)
    api.upload(ws, "organiser-update-3.txt", UPDATE)

    _, body, _ = timeline(api, ws)

    # One undated source means the source-date rule can't order everything: upload order, named.
    assert body["selection_rule"] == "latest_upload"
    events = body["events"]
    assert [e["filename"] for e in events] == [
        "project-brief-v1.md",
        "hallway.txt",
        "organiser-update-3.txt",
    ]
    assert events[1]["dated"] is False
    assert events[1]["order_label"] == "undated · uploaded 2nd"
    assert [e["changed"] for e in events] == [False, True, True]


def test_a_single_source_is_a_timeline_without_a_change_or_a_conflict(api):
    ws = api.new_workspace()
    api.upload(ws, "project-brief-v1.md", BRIEF)

    _, body, _ = timeline(api, ws)

    [event] = body["events"]
    assert event["changed"] is False and event["conflict_ids"] == [] and event["selected"] is True


def test_an_unknown_fact_is_a_400_and_names_the_facts_there_are(api):
    ws = api.new_workspace()
    status, body, _ = timeline(api, ws, "subject=submission&attribute=colour")
    assert status == 400 and body["error"]["code"] == "invalid_request"
    assert "submission/deadline" in body["error"]["message"]
    status, body, _ = timeline(api, ws, "")
    assert status == 400


def test_the_timeline_never_crosses_workspaces(api):
    a = api.new_workspace()
    b = api.new_workspace()
    api.upload(a, "project-brief-v1.md", BRIEF)
    api.upload(a, "organiser-update-3.txt", UPDATE)

    _, body, _ = timeline(api, b)
    assert body["events"] == []
    status, _, _ = timeline(api, "ws_doesnotexist000000000")
    assert status == 404
