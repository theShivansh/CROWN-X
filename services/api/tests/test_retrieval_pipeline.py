"""The retrieval pipeline after ADR-017: query-kind embeddings, near-duplicate removal, the optional
cross-encoder rerank, and the comparison modes the evaluation uses."""

from __future__ import annotations

from dataclasses import replace

from crownx.domain.fusion import near_duplicates

BRIEF = b"""# FestPass project brief

## Timeline

Final submissions close on 20 September 2026.

## Budget

Budget cap: 50,000 rupees from the Innovation Cell grant.

## Team

Four students build the ticketing app for the college fest.
"""


def ask(api, ws, question="When do final submissions close?"):
    status, body, _ = api.call("POST", f"/workspaces/{ws}/query", {"question": question})
    assert status == 200, body
    return body


# ---------------------------------------------------------------- dedup


def test_near_duplicates_of_one_document_are_dropped_keeping_the_better_rank():
    text = "Final submissions close on 20 September 2026 for every team."
    dropped = near_duplicates(
        [("a:1", "a", text), ("a:2", "a", text + " "), ("a:3", "a", "Budget cap is 50,000.")]
    )
    assert dropped == {"a:2"}


def test_the_same_words_in_two_documents_are_both_kept():
    text = "Final submissions close on 20 September 2026."
    assert near_duplicates([("a:1", "a", text), ("b:1", "b", text)]) == set()


def test_below_the_threshold_both_passages_stay():
    assert (
        near_duplicates(
            [("a:1", "a", "one two three four"), ("a:2", "a", "one two three five")], 0.9
        )
        == set()
    )


# ---------------------------------------------------------------- embeddings


def test_the_question_is_embedded_as_a_query_and_chunks_as_passages(api):
    ws = api.new_workspace()
    api.upload(ws, "brief.md", BRIEF)
    assert api.embedder.kinds == ["passage"]
    ask(api, ws)
    assert api.embedder.kinds == ["passage", "query"]


# ---------------------------------------------------------------- rerank


class ReverseReranker:
    """Scores passages by how late they came: the rerank visibly reverses the fused order."""

    model_id = "reverse"

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def scores(self, question, passages):
        self.calls.append((question, list(passages)))
        return [float(i) for i in range(len(passages))]


class BrokenReranker:
    model_id = "broken"

    def scores(self, question, passages):
        raise RuntimeError("model file missing")


def _chunks_in_order(body):
    return [e["chunk_id"] for e in body["evidence"]]


def test_the_reranker_reorders_candidates_and_evidence_ids_follow_the_new_order(api):
    ws = api.new_workspace()
    api.upload(ws, "brief.md", BRIEF)
    api.worker._target_chars, api.worker._overlap_chars = 60, 10  # several chunks to reorder
    api.upload(ws, "brief-small.md", BRIEF.replace(b"FestPass", b"FestPass small"))
    fused = _chunks_in_order(ask(api, ws))

    reranker = ReverseReranker()
    api.service._reranker = reranker
    reranked = ask(api, ws)
    [(question, passages)] = reranker.calls
    assert question == "When do final submissions close?"
    assert len(passages) >= len(fused)
    assert _chunks_in_order(reranked) != fused
    assert [e["evidence_id"] for e in reranked["evidence"]] == [
        f"ev_{n}" for n in range(1, len(reranked["evidence"]) + 1)
    ]
    assert [e["retrieval_rank"] for e in reranked["evidence"]] == list(
        range(1, len(reranked["evidence"]) + 1)
    )


def test_a_failing_reranker_keeps_the_fused_order(api):
    ws = api.new_workspace()
    api.upload(ws, "brief.md", BRIEF)
    fused = _chunks_in_order(ask(api, ws))
    api.service._reranker = BrokenReranker()
    assert _chunks_in_order(ask(api, ws)) == fused


# ---------------------------------------------------------------- comparison modes


def test_bm25_mode_never_embeds_and_dense_mode_never_runs_bm25(api):
    ws = api.new_workspace()
    api.upload(ws, "brief.md", BRIEF)

    api.service._limits = replace(api.service._limits, retrieval_mode="bm25")
    api.index.bodies.clear()
    before = len(api.embedder.calls)
    assert ask(api, ws)["evidence"]
    assert len(api.embedder.calls) == before
    assert [("knn" in b["query"]) for b in api.index.bodies] == [False]

    api.service._limits = replace(api.service._limits, retrieval_mode="dense")
    api.index.bodies.clear()
    assert ask(api, ws)["evidence"]
    assert [("knn" in b["query"]) for b in api.index.bodies] == [True]
