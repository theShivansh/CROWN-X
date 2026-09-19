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

from metrics import (  # noqa: E402
    NOT_MEASURED,
    case_checks,
    percentile,
    retrieval_metrics,
    summarize,
)

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


def test_mock_runs_never_report_live_metrics_and_m3_is_scored_apart():
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
    assert summary["m3"]["cases"] == 1
    assert summary["offline"]["retrieval"]["semantic"] is False
    assert all(value == NOT_MEASURED for value in summary["live"].values())


def test_a_deployed_run_with_real_providers_fills_the_live_section():
    providers = {
        "answer_provider": "groq",
        "answer_model": "openai/gpt-oss-120b",
        "embedding_provider": "onnx",
    }
    summary = summarize([CASE], {"c1": outcome()}, providers, live=True)
    live = summary["live"]
    assert live["recall_at_8"] == 1.0 and live["mrr"] == 0.5 and live["p95_answer_ms"] == 20.0
    assert live["groundedness"] == 1.0
    assert summary["offline"]["retrieval"]["semantic"] is True


def test_real_providers_offline_never_fill_the_live_section():
    providers = {"answer_provider": "groq", "embedding_provider": "onnx"}
    summary = summarize([CASE], {"c1": outcome()}, providers, live=False)
    assert all(value == NOT_MEASURED for value in summary["live"].values())


def test_retrieval_metrics_count_hits_recall_and_rank():
    case = {**CASE, "expected_files": ["a.md", "b.md"]}
    got = retrieval_metrics(
        [case],
        {
            "c1": {
                "evidence": [{"filename": f} for f in ["x", "a.md", "y", "z", "w", "b.md"]],
                "timings_ms": {"query": 12.0},
            }
        },
    )
    assert got["hit_rate_at_5"] == 1.0 and got["mrr"] == 0.5
    assert got["recall_at_5"] == 0.5 and got["recall_at_8"] == 1.0
    assert got["p50_query_ms"] == 12.0


def test_passage_metrics_judge_passages_and_break_down_by_category():
    from metrics import passage_metrics

    cases = [
        {"id": "a", "category": "original", "relevant_passages": ["f.md#One", "f.md#Two"]},
        {"id": "b", "category": "hinglish", "relevant_passages": ["g.md#Three"]},
    ]
    same_file_wrong_section = {"filename": "f.md", "page_or_section": "Zero"}
    outcomes = {
        "a": {
            "evidence": [same_file_wrong_section, {"filename": "f.md", "page_or_section": "One"}]
            + [{"filename": "x.md", "page_or_section": "X"}] * 4
            + [{"filename": "f.md", "page_or_section": "Two"}],
            "timings_ms": {"query": 10.0},
        },
        "b": {"evidence": [same_file_wrong_section], "timings_ms": {"query": 30.0}},
    }
    got = passage_metrics(cases, outcomes)
    assert got["recall_at_5"] == 0.25 and got["recall_at_8"] == 0.5  # (0.5 + 0) / 2, (1 + 0) / 2
    assert got["mrr"] == 0.25  # (1/2 + 0) / 2: a right file in the wrong section doesn't count
    assert got["by_category"]["hinglish"]["mrr"] == 0.0
    assert got["by_category"]["original"]["recall_at_8"] == 1.0
    assert got["p95_query_ms"] == 30.0


def test_retrieval_benchmark_v2_is_60_passages_and_30_labelled_queries():
    from collections import Counter

    import run

    from crownx.domain.chunking import chunk_text, normalize_text

    passages = {
        f"{path.name}#{chunk.section}"
        for path in run.RETRIEVAL_V2_CORPUS.glob("*.md")
        for chunk in chunk_text(normalize_text(path.read_text(encoding="utf-8")))
    }
    assert len(passages) == run.RETRIEVAL_V2_PASSAGES == 60
    cases = run.load_cases(run.RETRIEVAL_V2)
    assert Counter(c["category"] for c in cases) == {
        "original": 10,
        "paraphrased": 8,
        "hinglish": 6,
        "indirect": 3,
        "hard_negative": 3,
    }
    assert len({c["id"] for c in cases}) == 30
    for case in cases:
        assert case["relevant_passages"] and set(case["relevant_passages"]) <= passages, case["id"]


def test_percentile_is_nearest_rank():
    assert percentile([10, 20, 30, 40], 50) == 20 and percentile([10, 20, 30, 40], 95) == 40
    assert percentile([], 50) == NOT_MEASURED


def test_the_offline_run_holds_every_security_property():
    import run

    report = run.evaluate(run.InProcessClient(), "offline", timeout_s=5)
    offline = report["offline"]
    # The production Groq adapter answers, over the scripted transport: no network, no rate limit.
    assert report["providers"]["answer_provider"] == "groq"
    assert report["providers"]["answer_transport"].startswith("mock")
    assert all(v == "not measured" for v in report["live"].values())
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
    assert report["m3"]["cases"] >= 5
    # M3: exactly SCENARIO §3's six conflicts, no false one, and the right value and rule per key.
    contradictions = report["contradictions"]
    assert contradictions["contradiction_precision"] == 1.0
    assert contradictions["contradiction_recall"] == 1.0
    assert contradictions["format_equal_flagged"] == 0
    assert contradictions["selection_accuracy"] == 1.0
    assert contradictions["extraction"]["recall"] == 1.0


def test_contradiction_metrics_count_pairs_selection_and_extraction_bands():
    from metrics import contradiction_metrics

    cases = [
        {
            "expected_conflict": {
                "key": "k/a",
                "pairs": [["x.md", "y.md"]],
                "not_pairs": [["y.md", "z.md"]],
                "selected_normalized": "2",
                "rule": "newest_source_timestamp",
            }
        }
    ]

    def claim(cid, filename, value, confidence):
        return {"claim_id": cid, "filename": filename, "subject": "k", "attribute": "a",
                "normalized_value": value, "confidence": {"extraction": confidence}}  # fmt: skip

    group = {
        "key": "k/a",
        "selected_value": "2",
        "selection_rule": "newest_source_timestamp",
        "claims": [
            claim("c1", "x.md", "1", 1.0),
            claim("c2", "y.md", "2", 0.81),
            claim("c3", "z.md", "3", 0.9),
        ],  # fmt: skip
        "pairs": [
            {"claim_a": "c1", "claim_b": "c2"},
            {"claim_a": "c2", "claim_b": "c3"},  # a format-equal pair wrongly flagged
        ],
    }
    truth = [{"workspace": "A", "file": "x.md", "key": "k/a", "normalized_value": "1"},
             {"workspace": "A", "file": "y.md", "key": "k/a", "normalized_value": "2"}]  # fmt: skip
    got = contradiction_metrics(cases, {"A": [group]}, None, truth)
    assert got["contradiction_precision"] == 0.5 and got["contradiction_recall"] == 1.0
    assert got["format_equal_flagged"] == 1 and got["selection_accuracy"] == 1.0
    bands = got["extraction"]["precision_by_confidence"]
    assert bands["1.0"]["precision"] == 1.0 and bands["0.90-0.99"]["precision"] == 0.0
    assert got["extraction"]["recall"] == "not measured"  # a deployed run sees conflict claims only
