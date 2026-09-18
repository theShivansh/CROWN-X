"""The evaluation: exact metric functions, and the offline runner end to end (ADR-016).

The offline run is part of the M2 offline gate: it seeds the real corpus through the API handlers with
MockProvider, and its security properties must all hold. Mock answer quality is reported, not gated.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

EVALS = Path(__file__).resolve().parents[3] / "evals"
sys.path.insert(0, str(EVALS))

from metrics import NOT_MEASURED, case_checks, percentile, summarize  # noqa: E402

CASE = {
    "id": "c1",
    "category": "exact_lookup",
    "milestone": "M2",
    "workspace": "A",
    "question": "q",
    "expected_statuses": ["grounded", "partial"],
    "expected_values": ["22 Sept"],
    "expected_files": ["organiser-update-3.txt"],
    "forbidden_values": ["1 October"],
}


def outcome(**overrides) -> dict:
    base = {
        "status": "grounded",
        "answer": "The deadline moves to 22 Sept.",
        "claims": [{"text": "The deadline moves to 22 Sept.", "evidence_ids": ["ev_2"]}],
        "answer_provider": "mock",
        "evidence": [
            {
                "evidence_id": "ev_1",
                "chunk_id": "doc_a:0",
                "document_id": "doc_a",
                "filename": "project-brief-v1.pdf",
                "quoted_span": "close on 20 September",
            },
            {
                "evidence_id": "ev_2",
                "chunk_id": "doc_b:0",
                "document_id": "doc_b",
                "filename": "organiser-update-3.txt",
                "quoted_span": "moves to 22 Sept",
            },
        ],
        "workspace_documents": ["doc_a", "doc_b"],
        "timings_ms": {"query": 10.0, "answer": 20.0},
    }
    return {**base, **overrides}


def test_a_correct_case_passes_with_its_rank():
    checks = case_checks(CASE, outcome())
    assert checks["passed"] and checks["first_relevant_rank"] == 2


@pytest.mark.parametrize(
    ("overrides", "flag"),
    [
        ({"answer": "It is 1 October."}, "forbidden_absent"),
        ({"claims": [{"text": "x", "evidence_ids": ["ev_9"]}]}, "citations_valid"),
        ({"workspace_documents": ["doc_a"]}, "evidence_in_workspace"),
        ({"status": "insufficient_evidence"}, "status_ok"),
        ({"answer": "Soon.", "claims": [{"text": "Soon.", "evidence_ids": ["ev_2"]}]}, "values_ok"),
    ],
)
def test_each_exact_check_fails_the_case(overrides, flag):
    checks = case_checks(CASE, outcome(**overrides))
    assert checks[flag] is False and checks["passed"] is False


def test_cross_workspace_cases_also_check_the_evidence_text():
    case = {
        **CASE,
        "category": "cross_workspace",
        "forbidden_values": ["22 Sept"],
        "expected_values": [],
    }
    checks = case_checks(case, outcome(answer="", claims=[]))
    assert checks["forbidden_in_evidence"] == ["22 Sept"] and checks["security_ok"] is False


def test_zero_model_call_cases_need_no_provider_and_insufficient():
    case = {
        **CASE,
        "expect_no_model_call": True,
        "expected_statuses": ["insufficient_evidence"],
        "expected_values": [],
        "expected_files": [],
        "forbidden_values": [],
    }
    no_call = outcome(
        status="insufficient_evidence", answer="", claims=[], answer_provider=None, evidence=[]
    )
    assert case_checks(case, no_call)["zero_model_call_ok"]
    assert not case_checks(case, {**no_call, "answer_provider": "mock"})["zero_model_call_ok"]


def test_mock_runs_never_report_live_metrics_and_m3_is_excluded():
    m3 = {
        **CASE,
        "id": "m3",
        "milestone": "M3",
        "category": "date_conflict",
        "expected_statuses": ["conflict"],
    }
    summary = summarize(
        [CASE, m3],
        {"c1": outcome(), "m3": outcome()},
        {"answer_provider": "mock", "embedding_provider": "mock"},
    )
    assert summary["offline"]["m2_cases"] == 1 and summary["offline"]["m2_case_pass_rate"] == 1.0
    assert summary["m3_expected_fail"]["cases"] == 1
    assert summary["offline"]["retrieval"]["semantic"] is False
    assert all(value == NOT_MEASURED for value in summary["live_bedrock"].values())


def test_bedrock_runs_fill_the_live_section():
    summary = summarize(
        [CASE], {"c1": outcome()}, {"answer_provider": "bedrock", "embedding_provider": "bedrock"}
    )
    live = summary["live_bedrock"]
    assert live["recall_at_8"] == 1.0 and live["mrr"] == 0.5 and live["p95_answer_ms"] == 20.0
    assert live["groundedness"] == NOT_MEASURED  # needs the model grader and its agreement sample


def test_percentile_is_nearest_rank():
    assert percentile([10, 20, 30, 40], 50) == 20 and percentile([10, 20, 30, 40], 95) == 40
    assert percentile([], 50) == NOT_MEASURED


def test_the_offline_run_holds_every_security_property():
    import run

    report = run.evaluate(run.InProcessClient(), "offline", timeout_s=5)
    offline = report["offline"]
    assert report["providers"]["answer_provider"] == "mock"
    assert offline["m2_errors"] == 0 and offline["m2_cases"] >= 30
    assert report["security_gate_passed"], report["m2_failures"]
    for key in (
        "citation_validity",
        "evidence_id_integrity",
        "workspace_isolation_pass_rate",
        "injection_pass_rate",
        "zero_model_call_pass_rate",
    ):
        assert offline[key] == 1.0, key
    assert report["m3_expected_fail"]["cases"] >= 5
