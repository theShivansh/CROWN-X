"""Observability (ADR-017): environment and providers in /health, the structured logs, the audit
record and the answer response, including which model answered after a fallback."""

from __future__ import annotations

import json

from conftest import PROVIDERS

from crownx.adapters.groq import GroqAnswerer
from crownx.adapters.groq_mock import MockGroqTransport

BRIEF = b"# Brief\n\nFinal submissions close on 20 September 2026.\n"


def _ask_and_answer(api):
    ws = api.new_workspace()
    api.upload(ws, "brief.md", BRIEF)
    _, query, _ = api.call(
        "POST", f"/workspaces/{ws}/query", {"question": "When do submissions close?"}
    )
    status, body, _ = api.call("POST", f"/workspaces/{ws}/queries/{query['query_id']}/answer")
    return ws, status, body


def test_health_names_the_environment_and_every_provider(api):
    status, body, _ = api.call("GET", "/health")
    assert status == 200
    assert body["providers"] == PROVIDERS


def test_the_audit_record_names_environment_providers_and_the_answering_model(api):
    ws, status, _ = _ask_and_answer(api)
    assert status == 200
    [(audit_ws, audit)] = api.store.audit
    assert audit_ws == ws
    assert audit["environment"] == "test"
    assert audit["answer_provider"] == "fake"
    assert audit["embedding_provider"] == "fake"
    assert audit["embedding_model"] == "fake-embedder"
    assert audit["answered_by_model"] == "fake-answer-model"
    assert "Final submissions" not in json.dumps(audit)  # IDs and outcomes only, never text


def test_a_fallback_answer_says_which_model_wrote_it_everywhere(api, caplog):
    api.service._answerer = GroqAnswerer(
        "k",
        "openai/gpt-oss-120b",
        transport=MockGroqTransport("rate_limited_long"),
        fallback_model_id="openai/gpt-oss-20b",
        sleep=lambda _s: None,
    )
    _, status, body = _ask_and_answer(api)
    assert status == 200, body
    assert body["answered_by_model"] == "openai/gpt-oss-20b"
    assert [a["outcome"] for a in body["attempts"]] == ["rate_limited", "ok"]

    [(_, audit)] = api.store.audit
    assert audit["model_id"] == "openai/gpt-oss-120b"  # configured
    assert audit["answered_by_model"] == "openai/gpt-oss-20b"  # actually answered

    [written] = [r for r in caplog.records if r.getMessage() == "answer written"]
    assert written.answered_by_model == "openai/gpt-oss-20b"
    assert written.attempts[0]["outcome"] == "rate_limited"


def test_an_unavailable_answer_is_audited_with_its_attempts(api):
    api.service._answerer = GroqAnswerer(
        "k",
        "openai/gpt-oss-120b",
        transport=MockGroqTransport("all_fail"),
        fallback_model_id="openai/gpt-oss-20b",
        sleep=lambda _s: None,
    )
    ws, status, body = _ask_and_answer(api)
    assert status == 503
    assert body["error"]["code"] == "answer_unavailable"
    [(_, audit)] = api.store.audit
    assert audit["outcome"] == "error"
    assert [a["model_id"] for a in audit["attempts"]] == [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
    ]
    assert "answer_unavailable" in api.store.event_types(ws)


def test_an_unavailable_answer_logs_its_attempts(api, caplog):
    api.service._answerer = GroqAnswerer(
        "k",
        "openai/gpt-oss-120b",
        transport=MockGroqTransport("all_fail"),
        fallback_model_id="openai/gpt-oss-20b",
        sleep=lambda _s: None,
    )
    _, status, _ = _ask_and_answer(api)
    assert status == 503
    [logged] = [r for r in caplog.records if r.getMessage() == "answer not written"]
    assert [a["outcome"] for a in logged.attempts] == ["rate_limited", "http_500"]


def _finished(caplog) -> list:
    return [r for r in caplog.records if r.getMessage() == "request finished"]


def test_every_request_logs_its_route_status_latency_and_stages(api, caplog):
    ws, status, _ = _ask_and_answer(api)
    assert status == 200
    by_route = {r.route.split("/")[-1]: r for r in _finished(caplog)}
    query, answer = by_route["query"], by_route["answer"]
    assert query.status_code == 200 and isinstance(query.latency_ms, int)
    assert {"embed", "search", "compare"} <= set(query.stage_ms)
    assert set(answer.stage_ms) == {"answer_call"}
    upload = by_route["upload-url"]
    assert set(upload.stage_ms) == {"upload_url"}
    assert "Final submissions" not in str([r.__dict__ for r in _finished(caplog)])


def test_a_failed_request_logs_its_status_code(api, caplog):
    status, _, _ = api.call("GET", "/workspaces/ws_doesnotexist000000000/documents")
    assert status == 404
    [finished] = _finished(caplog)
    assert finished.status_code == 404 and finished.stage_ms == {}


def test_ingestion_logs_the_time_of_each_stage(api, caplog):
    ws = api.new_workspace()
    api.upload(ws, "brief.md", BRIEF)
    [stages] = [r for r in caplog.records if r.getMessage() == "ingestion stages"]
    assert set(stages.stage_ms) == {"read", "parse", "embed", "index", "claims"}
    assert stages.latency_ms == sum(stages.stage_ms.values())
