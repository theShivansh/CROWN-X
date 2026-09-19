"""The answer contract and the rules that turn a model's draft into what the user sees (ADR-002).

Code, not the model, decides the final status (CLAUDE.md rule 1, SECURITY T6):
- a claim that cites no evidence, or any ID that wasn't in the evidence the model was given, is dropped;
- the answer text is rebuilt from the kept claims only, so an unsupported sentence can't survive in
  free text beside them;
- a claim whose every citation is a passage carrying text addressed to an assistant (an injected
  instruction) is dropped too: that text is data, never a source of facts (rule 3);
- `grounded` when every claim survived, `partial` when some were dropped for missing or unknown
  citations, `insufficient_evidence` when none survived or the model said the evidence doesn't answer
  the question. A dropped instruction-only claim is recorded but doesn't make an answer partial: it was
  never a fact the reader lost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

from pydantic import BaseModel, ConfigDict, Field

INSUFFICIENT_ANSWER = (
    "Not enough evidence: no passage in this workspace answers the question. Upload a document that "
    "covers it, or ask about something the documents mention."
)


class ClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class AnswerDraft(BaseModel):
    """What an answer provider returns; the `submit_answer` tool's input schema (M2 prompt §4)."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(default="", max_length=4000)
    claims: list[ClaimDraft] = Field(default_factory=list, max_length=20)
    insufficient_evidence: bool = False


@dataclass(frozen=True)
class FinalAnswer:
    status: str  # "grounded" | "partial" | "insufficient_evidence"
    answer: str
    claims: list[dict]
    dropped: list[dict] = field(default_factory=list)


def insufficient() -> FinalAnswer:
    return FinalAnswer(status="insufficient_evidence", answer=INSUFFICIENT_ANSWER, claims=[])


def finalize(
    draft: AnswerDraft, allowed_ids: set[str], instruction_ids: frozenset[str] = frozenset()
) -> FinalAnswer:
    """`instruction_ids`: evidence IDs whose passage contains text addressed to an assistant."""
    kept: list[dict] = []
    dropped: list[dict] = []
    refused: list[dict] = []
    for claim in draft.claims:
        cited = list(dict.fromkeys(claim.evidence_ids))  # de-duplicated, order kept
        text = claim.text.strip()
        if not (text and cited and all(evidence_id in allowed_ids for evidence_id in cited)):
            dropped.append({"text": text, "evidence_ids": cited})
        elif all(evidence_id in instruction_ids for evidence_id in cited):
            refused.append({"text": text, "evidence_ids": cited, "reason": "instruction_only"})
        else:
            kept.append({"text": text, "evidence_ids": cited})
    if draft.insufficient_evidence or not kept:
        return FinalAnswer(
            status="insufficient_evidence",
            answer=INSUFFICIENT_ANSWER,
            claims=[],
            dropped=dropped + refused,
        )
    return FinalAnswer(
        status="partial" if dropped else "grounded",
        answer=" ".join(claim["text"] for claim in kept),
        claims=kept,
        dropped=dropped + refused,
    )


def render_evidence(evidence: list[dict]) -> str:
    """The evidence block for the user turn. Document text is data, never instructions (SECURITY T1).

    Attributes and body are XML-escaped, so a document containing `</evidence>` or a quote can't
    close its block early or forge another one.
    """
    blocks = []
    for item in evidence:
        attributes = {
            "id": item["evidence_id"],
            "document": item.get("filename") or item.get("document_id") or "",
            "version": item.get("version_label") or "",
            "date": item.get("source_timestamp") or "",
            "section": item.get("page_or_section") or "",
        }
        rendered = " ".join(
            f'{key}="{escape(str(value), quote=True)}"' for key, value in attributes.items()
        )
        blocks.append(
            f"<evidence {rendered}>\n{escape(item['quoted_span'], quote=False)}\n</evidence>"
        )
    return "\n\n".join(blocks)
