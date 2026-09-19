"""`POST /workspaces/{ws}/query`: fused evidence with IDs, spans, scores and ranks, never another
workspace's chunks, and an honest insufficient-evidence result."""

from __future__ import annotations

from conftest import TOP_K

from crownx.domain.ids import is_query_id

REQUEST_ID = "req_Tst123abc="

BRIEF = b"""# FestPass project brief

## Timeline

Final submissions close on 20 September 2026.

## Budget

Budget cap: \xe2\x82\xb950,000 (Innovation Cell grant).
"""
UPDATE = b"""Date: Thursday, 10 September 2026

The submission deadline for Campus Build Sprint moves to 22 Sept.

Teams also entering the Inter-College Robotics Expo: expo entries close on 21 Sept.
"""
MESSMATE = b"""# MessMate project brief

Submissions for Hostel Council Hack Week close on 25 September 2026.

Final demo: 26 September 2026, 3 PM, Seminar Hall B.
"""


def ask(api, ws: str, question: str):
    return api.call("POST", f"/workspaces/{ws}/query", {"question": question})


def test_query_returns_ranked_evidence_that_resolves_to_uploaded_chunks(api):
    ws = api.new_workspace()
    brief = api.upload(ws, "project-brief-v1.md", BRIEF)
    update = api.upload(ws, "organiser-update-3.txt", UPDATE)

    status, body, headers = ask(api, ws, "What is the submission deadline?")

    assert status == 200
    assert body["status"] == "retrieved"
    # M3: the brief's 20 September and the update's 22 Sept are one date conflict; the Robotics
    # Expo's 21 Sept is another key and never joins it.
    [conflict] = body["conflicts"]
    assert conflict["key"] == "submission/deadline" and len(conflict["pairs"]) == 1
    assert conflict["selected_value"] == "2026-09-22"
    assert conflict["selection_rule"] == "latest_upload"  # the .md brief here has no header date
    assert body["request_id"] == REQUEST_ID == headers["x-request-id"]
    evidence = body["evidence"]
    assert 1 <= len(evidence) <= TOP_K
    assert [e["retrieval_rank"] for e in evidence] == list(range(1, len(evidence) + 1))
    assert [e["evidence_id"] for e in evidence] == [f"ev_{n}" for n in range(1, len(evidence) + 1)]
    scores = [e["retrieval_score"] for e in evidence]
    assert scores == sorted(scores, reverse=True)
    names = {brief: "project-brief-v1.md", update: "organiser-update-3.txt"}
    for item in evidence:
        stored = api.index.chunks[item["chunk_id"]]
        assert item["document_id"] in names and item["filename"] == names[item["document_id"]]
        assert item["quoted_span"] == stored["text"]
        assert (item["char_start"], item["char_end"]) == (stored["char_start"], stored["char_end"])
    assert any("20 September 2026" in e["quoted_span"] for e in evidence)
    assert any("22 Sept" in e["quoted_span"] for e in evidence)


def test_both_retrieval_requests_carry_the_workspace_filter(api):
    ws = api.new_workspace()
    api.upload(ws, "brief.md", BRIEF)
    api.index.bodies.clear()
    ask(api, ws, "submission deadline")
    lexical, semantic = api.index.bodies
    scope = [
        {"term": {"workspace_id": ws}},
        {"term": {"embedding_provider": "fake"}},
        {"term": {"embedding_model": "fake-embedder"}},
        {"term": {"embedding_version": "1"}},
    ]
    assert lexical["query"]["bool"]["filter"] == scope
    assert semantic["query"]["knn"]["embedding"]["filter"] == {"bool": {"filter": scope}}
    # Each ranking contributes its candidate pool before fusion, dedup and rerank (ADR-017).
    assert lexical["size"] == semantic["size"] == max(15, TOP_K)


def test_a_fact_only_in_another_workspace_never_appears(api):
    team_a, team_b = api.new_workspace(), api.new_workspace()
    api.upload(team_a, "project-brief-v1.md", BRIEF)
    messmate = api.upload(team_b, "messmate-brief-v2.md", MESSMATE)

    _, in_a, _ = ask(api, team_a, "When is the MessMate final demo in Seminar Hall B?")
    assert all(e["document_id"] != messmate for e in in_a["evidence"])
    assert not any("Seminar Hall B" in e["quoted_span"] for e in in_a["evidence"])

    _, in_b, _ = ask(api, team_b, "When is the MessMate final demo in Seminar Hall B?")
    assert in_b["status"] == "retrieved"
    assert {e["document_id"] for e in in_b["evidence"]} == {messmate}


def test_nothing_relevant_is_insufficient_evidence(api):
    ws = api.new_workspace()
    status, body, _ = ask(api, ws, "What is the URL of the team's GitHub repository?")
    assert status == 200
    assert is_query_id(body.pop("query_id"))
    assert body == {
        "status": "insufficient_evidence",
        "evidence": [],
        "conflicts": [],
        "request_id": REQUEST_ID,
    }


def test_question_validation_and_unknown_workspace(api):
    ws = api.new_workspace()
    for payload in ({"question": ""}, {"question": "x" * 501}, {}, {"question": "ok", "k": 99}):
        status, body, _ = api.call("POST", f"/workspaces/{ws}/query", payload)
        assert status == 400 and body["error"]["code"] == "invalid_request"
    status, body, _ = ask(api, ws, "   ")
    assert status == 400 and body["error"]["request_id"] == REQUEST_ID
    status, body, _ = ask(api, "ws_" + "Q" * 22, "deadline?")
    assert status == 404 and body["error"]["code"] == "not_found"


def test_retrieval_outage_is_a_503_that_says_no_answer_was_attempted(api):
    ws = api.new_workspace()
    api.embedder.error = ConnectionError("AccessDeniedException: account being verified")
    status, body, _ = ask(api, ws, "What is the submission deadline?")
    assert status == 503
    assert body["error"]["code"] == "retrieval_unavailable"
    assert "AccessDenied" not in body["error"]["message"]
    assert body["error"]["request_id"] == REQUEST_ID


def test_a_leaked_chunk_from_another_workspace_fails_closed(api):
    team_a, team_b = api.new_workspace(), api.new_workspace()
    api.upload(team_b, "messmate.md", MESSMATE)
    original_search = api.index.search

    def unfiltered(body):  # simulate a store that ignored the filter

        body = {**body}
        if "knn" in body["query"]:
            knn = dict(body["query"]["knn"]["embedding"])
            knn.pop("filter")
            body["query"] = {"knn": {"embedding": knn}}
        else:
            body["query"] = {"bool": {**body["query"]["bool"], "filter": []}}
        return original_search(body)

    api.index.search = unfiltered
    status, body, _ = ask(api, team_a, "When is the final demo in Seminar Hall B?")
    assert status == 500
    assert "Seminar" not in str(body)
