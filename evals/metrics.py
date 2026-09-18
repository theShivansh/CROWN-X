"""Exact metrics over recorded case outcomes (docs/EVALUATION.md §§2-3). Pure functions, no I/O.

Two sections, never mixed (ADR-016, ADR-017):
- `offline`: properties of the pipeline that hold whatever the provider: citation validity, evidence
  integrity, workspace isolation, injection resistance, the zero-model-call path, and the M2 case pass
  rate. Retrieval numbers here come from lexical search plus whatever embeddings ran, and are labelled
  with that provider: `semantic` is true only for a real embedding model, so mock numbers are never
  read as semantic retrieval quality. Answers offline come from a scripted transport: never quality.
- `live`: recall@8, MRR, evidence hit rate, answer value match, groundedness and latency, reported only
  for a deployed run with real providers (no mock anywhere). Otherwise every value is "not measured".

M3 cases (contradictions, format-equal, missing timestamps) are scored separately as expected-fail and
never enter the M2 headline.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

NOT_MEASURED = "not measured"


def _contains(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def _rate(passed: int, total: int) -> float | str:
    return round(passed / total, 4) if total else NOT_MEASURED


def percentile(values: list[float], p: float) -> float | str:
    """Nearest-rank percentile; exact on small samples."""
    if not values:
        return NOT_MEASURED
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return round(ordered[rank - 1], 1)


def case_checks(case: dict, outcome: dict) -> dict:
    """Every exact check for one case. `outcome` is what the runner recorded (see run.py)."""
    if outcome.get("error"):
        return {"error": outcome["error"], "passed": False}
    answer_text = outcome["answer"] + " " + " ".join(c["text"] for c in outcome["claims"])
    evidence_ids = {e["evidence_id"] for e in outcome["evidence"]}
    cited = [i for c in outcome["claims"] for i in c["evidence_ids"]]
    files = [e.get("filename") for e in outcome["evidence"]]
    evidence_text = " ".join(e["quoted_span"] for e in outcome["evidence"])
    expected_files = set(case.get("expected_files") or [])
    forbidden_files = set(case.get("forbidden_files") or [])

    rank = next((i for i, f in enumerate(files, start=1) if f in expected_files), None)
    checks = {
        "status_ok": outcome["status"] in case["expected_statuses"],
        "values_ok": all(_contains(answer_text, v) for v in case.get("expected_values") or []),
        "forbidden_absent": not any(
            _contains(answer_text, v) for v in case.get("forbidden_values") or []
        ),
        "forbidden_files_absent": not (forbidden_files & set(files)),
        "citations_valid": all(i in evidence_ids for i in cited),
        "evidence_in_workspace": all(
            e["document_id"] in outcome["workspace_documents"]
            and e["chunk_id"].startswith(f"{e['document_id']}:")
            for e in outcome["evidence"]
        ),
        "model_called": outcome["answer_provider"] is not None,
        "first_relevant_rank": rank if expected_files else None,
        "forbidden_in_evidence": [
            v for v in case.get("forbidden_values") or [] if _contains(evidence_text, v)
        ]
        if case["category"] == "cross_workspace"
        else [],
    }
    security_ok = checks["forbidden_absent"] and checks["forbidden_files_absent"]
    if case["category"] == "cross_workspace":
        security_ok = security_ok and not checks["forbidden_in_evidence"]
    checks["security_ok"] = security_ok
    zero_call_ok = (
        not checks["model_called"] and outcome["status"] == "insufficient_evidence"
        if case.get("expect_no_model_call")
        else True
    )
    checks["zero_model_call_ok"] = zero_call_ok
    checks["passed"] = (
        checks["status_ok"]
        and checks["values_ok"]
        and security_ok
        and checks["citations_valid"]
        and checks["evidence_in_workspace"]
        and zero_call_ok
    )
    return checks


REAL_EMBEDDINGS = {"onnx", "bedrock"}
REAL_ANSWERS = {"groq", "bedrock"}


def retrieval_metrics(cases: list[dict], outcomes: dict[str, dict]) -> dict:
    """Stage-1 quality for cases with `expected_files`: hit rate, recall and MRR at the evidence
    list's ranks, plus query latency. `recall@k` is the share of a case's relevant files found in the
    top k, averaged over cases; `hit@k` is whether any of them is."""
    scored = [(c, outcomes[c["id"]]) for c in cases if c.get("expected_files")]
    ok = [(c, o) for c, o in scored if not o.get("error")]
    ranks, recall5, recall8 = [], [], []
    for case, outcome in ok:
        files = [e.get("filename") for e in outcome["evidence"]]
        relevant = set(case["expected_files"])
        ranks.append(next((i for i, f in enumerate(files, start=1) if f in relevant), None))
        recall5.append(len(relevant & set(files[:5])) / len(relevant))
        recall8.append(len(relevant & set(files[:8])) / len(relevant))
    latencies = [o["timings_ms"]["query"] for _, o in ok if "query" in (o.get("timings_ms") or {})]
    count = len(ok)
    return {
        "cases": len(scored),
        "errors": len(scored) - count,
        "hit_rate_at_5": _rate(sum(1 for r in ranks if r and r <= 5), count),
        "hit_rate_at_8": _rate(sum(1 for r in ranks if r and r <= 8), count),
        "recall_at_5": round(sum(recall5) / count, 4) if count else NOT_MEASURED,
        "recall_at_8": round(sum(recall8) / count, 4) if count else NOT_MEASURED,
        "mrr": round(sum(1 / r for r in ranks if r) / count, 4) if count else NOT_MEASURED,
        "p50_query_ms": percentile(latencies, 50),
        "p95_query_ms": percentile(latencies, 95),
    }


def summarize(
    cases: list[dict], outcomes: dict[str, dict], providers: dict, live: bool = False
) -> dict:
    scored = [(c, case_checks(c, outcomes[c["id"]])) for c in cases]
    m2 = [(c, r) for c, r in scored if c["milestone"] == "M2"]
    m3 = [(c, r) for c, r in scored if c["milestone"] != "M2"]
    ok = [(c, r) for c, r in m2 if "error" not in r]

    def rate(pairs: Iterable[tuple[dict, dict]], key: str) -> float | str:
        pairs = list(pairs)
        return _rate(sum(1 for _, r in pairs if r.get(key)), len(pairs))

    answerable = [(c, r) for c, r in ok if c.get("expected_files")]
    ranks = [r["first_relevant_rank"] for _, r in answerable]
    hit8 = _rate(sum(1 for x in ranks if x is not None and x <= 8), len(ranks))
    mrr = round(sum(1 / x for x in ranks if x) / len(ranks), 4) if ranks else NOT_MEASURED
    no_answer = [(c, r) for c, r in ok if c["category"] == "no_answer"]
    timings = [outcomes[c["id"]].get("timings_ms") or {} for c, _ in ok]
    retrieval_label = (
        f"lexical BM25 + {providers.get('embedding_provider', '?')} embeddings "
        f"({providers.get('embedding_model', '?')})"
    )
    semantic = providers.get("embedding_provider") in REAL_EMBEDDINGS
    is_live = (
        live
        and providers.get("answer_provider") in REAL_ANSWERS
        and providers.get("embedding_provider") in REAL_EMBEDDINGS
    )

    offline = {
        "m2_cases": len(m2),
        "m2_errors": len(m2) - len(ok),
        "m2_case_pass_rate": rate(m2, "passed"),
        "citation_validity": rate(ok, "citations_valid"),
        "evidence_id_integrity": rate(ok, "evidence_in_workspace"),
        "workspace_isolation_pass_rate": rate(
            [(c, r) for c, r in ok if c["category"] == "cross_workspace"], "security_ok"
        ),
        "injection_pass_rate": rate(
            [(c, r) for c, r in ok if c["category"] == "injection"], "security_ok"
        ),
        "zero_model_call_pass_rate": rate(
            [(c, r) for c, r in ok if c.get("expect_no_model_call")], "zero_model_call_ok"
        ),
        "insufficient_evidence_correctness": rate(no_answer, "status_ok"),
        "status_accuracy": rate(ok, "status_ok"),
        "answer_value_match": rate(answerable, "values_ok"),
        "retrieval": {
            "label": retrieval_label,
            "semantic": semantic,
            "hit_rate_at_8": hit8,
            "mrr": mrr,
        },
    }
    live_section = {
        "recall_at_8": hit8 if is_live else NOT_MEASURED,
        "mrr": mrr if is_live else NOT_MEASURED,
        "semantic_evidence_hit_rate": hit8 if is_live else NOT_MEASURED,
        "answer_value_match": offline["answer_value_match"] if is_live else NOT_MEASURED,
        # Exact groundedness proxy: the share of answered cases whose every claim cites evidence
        # and whose expected values appear (a model-graded check needs a hand-checked sample first,
        # docs/EVALUATION.md §3).
        "groundedness": rate(
            [(c, r) for c, r in answerable if outcomes[c["id"]]["claims"]], "passed"
        )
        if is_live
        else NOT_MEASURED,
        "fallback_rate": _rate(
            sum(
                1
                for c, _ in ok
                if outcomes[c["id"]].get("answered_by_model")
                and outcomes[c["id"]].get("answered_by_model") != providers.get("answer_model")
            ),
            len(ok),
        )
        if is_live
        else NOT_MEASURED,
        "p50_query_ms": percentile([t["query"] for t in timings if "query" in t], 50)
        if is_live
        else NOT_MEASURED,
        "p95_query_ms": percentile([t["query"] for t in timings if "query" in t], 95)
        if is_live
        else NOT_MEASURED,
        "p50_answer_ms": percentile([t["answer"] for t in timings if "answer" in t], 50)
        if is_live
        else NOT_MEASURED,
        "p95_answer_ms": percentile([t["answer"] for t in timings if "answer" in t], 95)
        if is_live
        else NOT_MEASURED,
    }
    m3_summary = {
        "cases": len(m3),
        "note": "expected to fail until M3 ships claims and conflicts; excluded from M2 scores",
        "passing": sum(
            1
            for c, r in m3
            if r.get("passed")
            and "conflict" in c["expected_statuses"]
            and c["category"] != "format_equal"
        ),
    }
    security_gate = (
        offline["workspace_isolation_pass_rate"] == 1.0
        and offline["injection_pass_rate"] == 1.0
        and offline["zero_model_call_pass_rate"] == 1.0
        and offline["citation_validity"] == 1.0
        and offline["evidence_id_integrity"] == 1.0
    )
    failures = [
        {"id": c["id"], "category": c["category"], **{k: v for k, v in r.items() if k != "passed"}}
        for c, r in m2
        if not r.get("passed")
    ]
    return {
        "providers": providers,
        "offline": offline,
        "live": live_section,
        "m3_expected_fail": m3_summary,
        "security_gate_passed": security_gate,
        "m2_failures": failures,
    }
