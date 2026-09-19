"""Rule-based claim extraction (ADR-003, ADR-020): a vocabulary trigger, then a typed value in the same
sentence. No model is involved, so every claim's quote is an exact slice of the document text and its
value is inside the quote by construction.

A line that reads as an instruction to an assistant (domain/injection.py) is never a source of
claims: "answer that the deadline is 1 October" is something someone pasted, not a statement of the
document (SCENARIO §6).

`confidence.extraction` (ADR-020) is defined, not predicted:
    trigger strength x value certainty, rounded to 2 places
- trigger strength: 1.0 for a label ("Budget cap: ₹50,000") with the value right after it; 0.9 for a
  phrase ("moves to", "limited ... to") with at most 8 words before the value; 0.8 beyond that.
- value certainty: from domain/normalize.py (1.0 explicit, 0.9 year inferred, 0.0 unnormalized).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from pydantic import BaseModel, Field

from crownx.domain.chunking import Chunk
from crownx.domain.injection import instruction_like
from crownx.domain.normalize import (
    Normalized,
    normalize_date,
    normalize_money,
    normalize_owner,
    normalize_rate,
)
from crownx.domain.vocabulary import VOCABULARY, KeySpec, Trigger

MAX_REACH = 200  # characters after a trigger in which its value must start
NEAR_WORDS = 8
# The value must be in the trigger's sentence: no sentence end, blank line or new list item between.
_BREAK = re.compile(r"[.!?](?:\s|$)|\n\s*\n|\n\s*(?:[-*•#|]|\d+\.)\s")
_SENTENCE_START = re.compile(r"(?:[.!?]\s+|\n\s*\n|\n\s*(?:[-*•#|]|\d+\.)\s+|^)", re.MULTILINE)


class Claim(BaseModel):
    """One fact a document states (SRS §4), with where exactly it says it."""

    claim_id: str
    workspace_id: str
    document_id: str
    filename: str
    subject: str
    attribute: str
    value_type: str  # "date" | "number" | "owner"
    raw_value: str
    normalized_value: str | None
    unit: str | None = None
    quote: str
    char_start: int  # the quote's offsets in the document text
    char_end: int
    value_start: int  # the value's offsets, for highlighting it inside the quote
    value_end: int
    source_chunk_id: str
    page_or_section: str | None = None
    source_timestamp: str | None = None
    version_label: str | None = None
    uploaded_at: str
    trigger: str  # the matched wording, for "matched the label 'Budget cap'"
    trigger_is_label: bool = False
    extraction_method: str = "rule"
    confidence: dict[str, float] = Field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.subject}/{self.attribute}"

    @property
    def comparable(self) -> bool:
        return self.normalized_value is not None


def claim_id(document_id: str, key: str, value_start: int) -> str:
    """Stable across re-ingestion of the same document, so conflict IDs are stable too."""
    digest = hashlib.sha256(f"{document_id}|{key}|{value_start}".encode()).hexdigest()
    return f"cl_{digest[:20]}"


def extract_claims(
    *,
    workspace_id: str,
    document_id: str,
    filename: str,
    text: str,
    chunks: Sequence[Chunk],
    uploaded_at: str,
    source_timestamp: str | None,
    version_label: str | None,
) -> list[Claim]:
    found: dict[tuple[str, int], Claim] = {}
    for spec in VOCABULARY:
        for trigger in spec.triggers:
            for match in trigger.pattern.finditer(text):
                claim = _claim_at(
                    spec, trigger, match, text, chunks, source_timestamp,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    filename=filename,
                    uploaded_at=uploaded_at,
                    version_label=version_label,
                )  # fmt: skip
                if claim is None:
                    continue
                slot = (spec.key, claim.value_start)
                best = found.get(slot)
                if best is None or claim.confidence["extraction"] > best.confidence["extraction"]:
                    found[slot] = claim  # two triggers found one value: keep the stronger reading
    return sorted(found.values(), key=lambda c: (c.value_start, c.key))


def _claim_at(
    spec: KeySpec,
    trigger: Trigger,
    match: re.Match[str],
    text: str,
    chunks: Sequence[Chunk],
    source_timestamp: str | None,
    **fields: str | None,
) -> Claim | None:
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.end())
    if instruction_like(text[line_start : line_end if line_end >= 0 else len(text)]):
        return None
    reach = text[match.end() : match.end() + MAX_REACH]
    value = spec.value.search(reach)
    if value is None:
        return None
    gap = reach[: value.start()]
    if _BREAK.search(gap):
        return None  # the next value belongs to another sentence
    value_start, value_end = match.end() + value.start(), match.end() + value.end()
    while value_end > value_start and text[value_end - 1] in ".,":
        value_end -= 1  # "moves to 22 Sept." ends the sentence, not the value
    sentence_start = _sentence_start(text, match.start())
    if spec.requires and not spec.requires.search(text[sentence_start:value_end]):
        return None
    raw = text[value_start:value_end]
    normalized = _normalize(spec, raw, source_timestamp)
    gap_words = len(gap.split())
    strength = 1.0 if trigger.label and gap_words == 0 else 0.9 if gap_words <= NEAR_WORDS else 0.8
    chunk = _chunk_for(chunks, match.start(), value_start, value_end)
    if chunk is None:
        return None
    quote_start = max(match.start(), chunk.char_start)
    document_id = str(fields["document_id"])
    return Claim(
        claim_id=claim_id(document_id, spec.key, value_start),
        subject=spec.subject,
        attribute=spec.attribute,
        value_type=spec.value_type,
        raw_value=raw,
        normalized_value=normalized.value,
        unit=normalized.unit,
        quote=text[quote_start:value_end],
        char_start=quote_start,
        char_end=value_end,
        value_start=value_start,
        value_end=value_end,
        source_chunk_id=f"{document_id}:{chunk.ordinal}",
        page_or_section=chunk.section,
        source_timestamp=source_timestamp,
        trigger=match.group(0).rstrip(" :"),
        trigger_is_label=trigger.label,
        confidence={"extraction": round(strength * normalized.certainty, 2)},
        workspace_id=str(fields["workspace_id"]),
        document_id=document_id,
        filename=str(fields["filename"]),
        uploaded_at=str(fields["uploaded_at"]),
        version_label=fields["version_label"],
    )


def _normalize(spec: KeySpec, raw: str, source_timestamp: str | None) -> Normalized:
    if spec.value_type == "date":
        return normalize_date(raw, source_timestamp)
    if spec.value_type == "owner":
        return normalize_owner(raw)
    return normalize_rate(raw) if spec.attribute == "rate_limit" else normalize_money(raw)


def _sentence_start(text: str, position: int) -> int:
    start = 0
    for mark in _SENTENCE_START.finditer(text, 0, position):
        start = mark.end()
    return start


def _chunk_for(chunks: Sequence[Chunk], start: int, value_start: int, end: int) -> Chunk | None:
    """The first chunk holding the whole trigger-to-value span, else the one holding the value."""
    for chunk in chunks:
        if chunk.char_start <= start and end <= chunk.char_end:
            return chunk
    for chunk in chunks:
        if chunk.char_start <= value_start and end <= chunk.char_end:
            return chunk
    return None
