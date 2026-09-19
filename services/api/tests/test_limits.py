"""Cost limits (M4, SECURITY T7): over a limit is a 413 or 429 with the SRS error, and nothing past
the check runs, so no embedding, search or model call is spent on it."""

from __future__ import annotations

from dataclasses import replace

from test_conflicts_api import BRIEF


def _tight(api, per_hour: int) -> None:
    api.service._limits = replace(api.service._limits, questions_per_hour=per_hour)


def test_questions_over_the_hourly_limit_are_429_before_any_retrieval(api):
    ws = api.new_workspace()
    api.upload(ws, "project-brief-v1.md", BRIEF)
    _tight(api, 2)
    searches = []
    search = api.index.search
    api.index.search = lambda body: searches.append(body) or search(body)

    for _ in range(2):
        status, body, _ = api.call(
            "POST", f"/workspaces/{ws}/query", {"question": "When is the deadline?"}
        )
        assert status == 200, body
    status, body, _ = api.call(
        "POST", f"/workspaces/{ws}/query", {"question": "When is the deadline?"}
    )

    assert status == 429
    assert body["error"]["code"] == "limit_reached"
    assert "2 questions for this hour" in body["error"]["message"]
    assert body["error"]["request_id"]
    per_question = len(searches) // 2  # the refused third question never searched
    assert per_question >= 1 and len(searches) == 2 * per_question


def test_the_limit_is_per_workspace(api):
    a = api.new_workspace()
    b = api.new_workspace()
    _tight(api, 1)
    assert api.call("POST", f"/workspaces/{a}/query", {"question": "deadline?"})[0] == 200
    assert api.call("POST", f"/workspaces/{a}/query", {"question": "deadline?"})[0] == 429
    assert api.call("POST", f"/workspaces/{b}/query", {"question": "deadline?"})[0] == 200


def test_repeated_answers_to_one_query_are_counted_as_model_calls(api):
    ws = api.new_workspace()
    api.upload(ws, "project-brief-v1.md", BRIEF)
    _, query, _ = api.call(
        "POST", f"/workspaces/{ws}/query", {"question": "When do submissions close?"}
    )
    _tight(api, 2)
    calls_before = len(api.answerer.calls)

    path = f"/workspaces/{ws}/queries/{query['query_id']}/answer"
    assert api.call("POST", path)[0] == 200
    assert api.call("POST", path)[0] == 200
    status, body, _ = api.call("POST", path)

    assert status == 429 and body["error"]["code"] == "limit_reached"
    assert len(api.answerer.calls) == calls_before + 2  # the refused one never reached the model


def test_an_oversize_upload_is_413_and_a_long_question_400(api):
    ws = api.new_workspace()
    limit = api.service._limits.max_upload_bytes
    status, body, _ = api.call(
        "POST",
        f"/workspaces/{ws}/documents/upload-url",
        {"filename": "big.pdf", "size_bytes": limit + 1},
    )
    assert status == 413 and body["error"]["code"] == "too_large"
    status, body, _ = api.call("POST", f"/workspaces/{ws}/query", {"question": "x" * 501})
    assert status == 400 and body["error"]["code"] == "invalid_request"
