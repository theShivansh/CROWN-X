"""MockProvider (ADR-016): deterministic embeddings and answers with no model and no network.

Allowed only in `development`, `test` and an explicit `offline-demo` (config.py refuses it in
production). It exists so the whole pipeline, the UI and the offline evaluation run while Bedrock is
unavailable. Its numbers are never reported as semantic retrieval or answer quality.

- `MockEmbedder`: hashed bag of words, normalized, at the same dimension as Titan V2 so it shares the
  one index; the embedding namespace keeps its vectors apart from Bedrock's.
- `MockAnswerer`: extractive. It picks the sentences from the given evidence that share the most words
  with the question and cites the passage each came from, so it can't cite an ID it wasn't given.
"""

from __future__ import annotations

import hashlib
import math
import re
import time

from crownx.adapters.ports import AnswerResult
from crownx.domain.answering import AnswerDraft, ClaimDraft

MOCK_EMBEDDING_MODEL = "mock-hashed-bow"
MOCK_ANSWER_MODEL = "mock-extractive"

_WORD = re.compile(r"[a-z0-9₹]+(?:[.,][0-9]+)*", re.IGNORECASE)
_STOP = frozenset(
    "a an and are as at be by current currently do does for from how in is it of on or our the this "
    "to was we what when where which who whom why will with".split()
)
_SENTENCE = re.compile(r"[^\n.!?]+(?:[.!?](?=\s|$)|$)")
# Text addressed to an assistant is content to describe, never a claim to repeat (SECURITY T1).
_INSTRUCTION = re.compile(
    r"\b(ignore (all |any )?(previous|prior|above) instructions|disregard (the |your )?(rules|instructions)"
    r"|you are now|answer that)\b",
    re.IGNORECASE,
)
MAX_CLAIMS = 3


def words(text: str) -> list[str]:
    return [w for w in (m.group(0).lower() for m in _WORD.finditer(text)) if w not in _STOP]


class MockEmbedder:
    provider = "mock"
    model_id = MOCK_EMBEDDING_MODEL

    def __init__(self, dimensions: int = 1024) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for word in words(text):
                digest = hashlib.sha256(word.encode()).digest()
                vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 1.0
            norm = math.sqrt(sum(v * v for v in vector))
            if norm == 0:
                vector[0], norm = 1.0, 1.0  # no content words: a fixed direction, never all zeros
            vectors.append([v / norm for v in vector])
        return vectors


class MockAnswerer:
    provider = "mock"
    model_id = MOCK_ANSWER_MODEL

    def answer(self, question: str, evidence: list[dict]) -> AnswerResult:
        started = time.perf_counter()
        asked = set(words(question))
        picked: list[tuple[int, int, str, str]] = []  # (-score, rank, sentence, evidence_id)
        for rank, item in enumerate(evidence):
            best = _best_sentence(item["quoted_span"], asked)
            if best:
                score, sentence = best
                picked.append((-score, rank, sentence, item["evidence_id"]))
        picked.sort()
        claims = [
            ClaimDraft(text=sentence, evidence_ids=[evidence_id])
            for _, _, sentence, evidence_id in picked[:MAX_CLAIMS]
        ]
        draft = AnswerDraft(
            answer=" ".join(c.text for c in claims),
            claims=claims,
            insufficient_evidence=not claims,
        )
        return AnswerResult(
            draft=draft,
            provider=self.provider,
            model_id=self.model_id,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )


def _best_sentence(span: str, asked: set[str]) -> tuple[int, str] | None:
    best: tuple[int, str] | None = None
    for match in _SENTENCE.finditer(span):
        sentence = re.sub(r"^[\s#>*|-]+", "", match.group(0)).strip()
        if not sentence or _INSTRUCTION.search(sentence):
            continue
        score = len(asked & set(words(sentence)))
        if score and (best is None or score > best[0]):
            best = (score, sentence)
    return best
