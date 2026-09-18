"""A local stand-in for OpenSearch in offline evaluations (ADR-017): real BM25 and exact dense search.

- Lexical: `rank_bm25.BM25Okapi` over the chunks that pass the request's filters (so IDF is computed
  per workspace and embedding namespace), with the tokenizer below.
- Dense: FAISS `IndexFlatIP` over the same filtered chunks. Vectors are L2-normalised, so inner
  product is cosine similarity, the same space the deployed Lucene HNSW index uses (`cosinesimil`).

It implements the `SearchIndex` port and honours the filters exactly as written in the request body,
like the test double does, so a request that forgot the workspace filter would see every workspace.
Evaluation only: never imported by deployed code.
"""

from __future__ import annotations

import re

import numpy as np
from crownx.adapters.ports import SearchHit

_TOKEN = re.compile(r"\b[a-zA-Z0-9_./:-]+\b")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _matches(clause: dict | None, chunk: dict) -> bool:
    if not clause:
        return True
    if "term" in clause:
        [(field, value)] = clause["term"].items()
        return chunk.get(field) == value
    if "bool" in clause:
        return all(_matches(inner, chunk) for inner in clause["bool"].get("filter", []))
    raise AssertionError(f"LocalHybridIndex doesn't understand {clause}")


class LocalHybridIndex:
    def __init__(self) -> None:
        self.chunks: dict[str, dict] = {}
        self.created_with: dict | None = None

    def index_exists(self) -> bool:
        return True

    def ensure_index(self, body: dict) -> bool:
        created = self.created_with is None
        self.created_with = self.created_with or body
        return created

    def index_chunks(self, chunks: list[dict]) -> None:
        for chunk in chunks:
            self.chunks[chunk["chunk_id"]] = dict(chunk)

    def search(self, body: dict) -> list[SearchHit]:
        query = body["query"]
        if "knn" in query:
            clause = query["knn"]["embedding"]
            candidates = [c for c in self.chunks.values() if _matches(clause.get("filter"), c)]
            scored = self._dense(candidates, clause["vector"], body["size"])
        else:
            filters = {"bool": {"filter": query["bool"].get("filter", [])}}
            candidates = [c for c in self.chunks.values() if _matches(filters, c)]
            text = query["bool"]["must"][0]["match"]["text"]["query"]
            scored = self._bm25(candidates, text, body["size"])
        return [
            SearchHit(
                chunk_id=c["chunk_id"],
                score=float(s),
                source={k: v for k, v in c.items() if k != "embedding"},
            )
            for s, c in scored
        ]

    @staticmethod
    def _bm25(candidates: list[dict], text: str, size: int) -> list[tuple[float, dict]]:
        from rank_bm25 import BM25Okapi

        words = tokenize(text)
        if not candidates or not words:
            return []
        scores = BM25Okapi([tokenize(c["text"]) or [""] for c in candidates]).get_scores(words)
        # BM25Okapi can give a matching term a zero or negative IDF on a tiny corpus; keep any chunk
        # that shares a word with the question, like OpenSearch's `match` does.
        asked = set(words)
        ranked = [
            (float(score), chunk)
            for score, chunk in zip(scores, candidates, strict=True)
            if asked & set(tokenize(chunk["text"]))
        ]
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["chunk_id"]))
        return ranked[:size]

    @staticmethod
    def _dense(candidates: list[dict], vector: list[float], size: int) -> list[tuple[float, dict]]:
        import faiss

        candidates = [c for c in candidates if len(c["embedding"]) == len(vector)]
        if not candidates:
            return []
        matrix = np.array([c["embedding"] for c in candidates], dtype=np.float32)
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        scores, rows = index.search(
            np.array([vector], dtype=np.float32), min(size, len(candidates))
        )
        ranked = [
            (float(s), candidates[int(r)])
            for s, r in zip(scores[0], rows[0], strict=True)
            if r >= 0
        ]
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["chunk_id"]))
        return ranked
