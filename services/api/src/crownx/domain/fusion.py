"""Reciprocal rank fusion of the lexical and semantic rankings (M1, k = 60)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FusedHit:
    chunk_id: str
    score: float
    rank: int


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], k: int = 60, top_k: int | None = None
) -> list[FusedHit]:
    """score(d) = sum over rankings of 1 / (k + rank of d), with ranks starting at 1.

    Ties break deterministically: first by the best rank the chunk reached in any single ranking,
    then by chunk ID, so the same inputs always give the same order.
    """
    scores: dict[str, float] = {}
    best_rank: dict[str, int] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for position, chunk_id in enumerate(ranking, start=1):
            if chunk_id in seen:
                continue  # a ranking lists each chunk once
            seen.add(chunk_id)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + position)
            best_rank[chunk_id] = min(best_rank.get(chunk_id, position), position)
    ordered = sorted(scores, key=lambda cid: (-scores[cid], best_rank[cid], cid))
    if top_k is not None:
        ordered = ordered[:top_k]
    return [
        FusedHit(chunk_id=cid, score=scores[cid], rank=n) for n, cid in enumerate(ordered, start=1)
    ]
