"""Reciprocal rank fusion of the lexical and semantic rankings (M1, k = 60), and near-duplicate
removal before the evidence is shown (ADR-017)."""

from __future__ import annotations

import re
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


_TOKEN = re.compile(r"[a-z0-9₹]+", re.IGNORECASE)


def near_duplicates(passages: Sequence[tuple[str, str, str]], threshold: float = 0.9) -> set[str]:
    """Chunk IDs to drop because a better-ranked passage of the same document says the same thing.

    `passages` are (chunk_id, document_id, text) in rank order. Two passages are near-duplicates when
    the Jaccard similarity of their word sets is at least `threshold`; the later one is dropped, so the
    better rank always survives. Passages from different documents are never merged: two versions
    stating the same value are evidence of agreement, which M3 needs to see.
    """
    kept: list[tuple[str, frozenset[str]]] = []
    dropped: set[str] = set()
    for chunk_id, document_id, text in passages:
        words = frozenset(t.lower() for t in _TOKEN.findall(text))
        if any(doc == document_id and _jaccard(words, other) >= threshold for doc, other in kept):
            dropped.add(chunk_id)
        else:
            kept.append((document_id, words))
    return dropped


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)
