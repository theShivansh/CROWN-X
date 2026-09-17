"""Reciprocal rank fusion (k = 60): exact scores and a deterministic order, ties included."""

from __future__ import annotations

import pytest

from crownx.domain.fusion import reciprocal_rank_fusion


def test_scores_follow_the_formula_and_agreement_wins():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]], k=60)
    by_id = {hit.chunk_id: hit for hit in fused}
    assert by_id["b"].score == pytest.approx(1 / 62 + 1 / 61)
    assert by_id["a"].score == pytest.approx(1 / 61)
    assert fused[0].chunk_id == "b"
    assert [hit.rank for hit in fused] == list(range(1, len(fused) + 1))


def test_ties_break_by_best_single_rank_then_id():
    # a and x both appear once at rank 1; c and y both once at rank 2.
    fused = reciprocal_rank_fusion([["x", "y"], ["a", "c"]], k=60)
    assert [hit.chunk_id for hit in fused] == ["a", "x", "c", "y"]


def test_order_is_identical_whichever_ranking_comes_first():
    lexical, semantic = ["c1", "c2", "c3", "c4"], ["c4", "c3", "c9"]
    first = reciprocal_rank_fusion([lexical, semantic])
    second = reciprocal_rank_fusion([semantic, lexical])
    assert [(h.chunk_id, h.score) for h in first] == [(h.chunk_id, h.score) for h in second]


def test_top_k_bounds_the_result_and_empty_input_is_empty():
    assert len(reciprocal_rank_fusion([["a", "b", "c"], ["d", "e"]], top_k=2)) == 2
    assert reciprocal_rank_fusion([[], []]) == []


def test_a_repeated_id_in_one_ranking_counts_once():
    fused = reciprocal_rank_fusion([["a", "a", "b"]], k=60)
    assert {h.chunk_id: h.score for h in fused} == {
        "a": pytest.approx(1 / 61),
        "b": pytest.approx(1 / 63),
    }
