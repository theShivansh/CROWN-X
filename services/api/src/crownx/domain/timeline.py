"""How one fact's value changed across the workspace's sources (FR-09, UI_UX §3.6). Pure.

The events are ordered by `selection.select`, the same function that picks the current value, so the
timeline and the conflict inspector can never disagree about which source is newer. Only comparable
(normalized) claims take part, as in the predicate; a document that states one value twice is one
event.
"""

from __future__ import annotations

from collections.abc import Iterable

from crownx.domain.claims import Claim
from crownx.domain.conflicts import conflict_id, conflicts_between, one_per_document_value
from crownx.domain.selection import select
from crownx.domain.vocabulary import PLAIN_KEY, VOCABULARY

KEYS = {spec.subject + "/" + spec.attribute: spec for spec in VOCABULARY}

_ORDINAL = {1: "1st", 2: "2nd", 3: "3rd"}


def _ordinal(n: int) -> str:
    return _ORDINAL.get(n, f"{n}th")


def timeline(claims: Iterable[Claim], key: str) -> dict:
    """The `/timeline` shape: the key, the rule, and one event per source, oldest first."""
    members = [c for c in one_per_document_value(claims) if c.key == key and c.comparable]
    selection = select(members)
    uploads = sorted(members, key=lambda c: (c.uploaded_at or "", c.value_start))
    upload_rank = {c.claim_id: i + 1 for i, c in enumerate(uploads)}
    events = []
    previous: Claim | None = None
    for claim in selection.ordered:
        conflicts = sorted(
            conflict_id(claim, other)
            for other in members
            if other.claim_id != claim.claim_id and conflicts_between(claim, other)
        )
        events.append(
            {
                "claim_id": claim.claim_id,
                "document_id": claim.document_id,
                "filename": claim.filename,
                "version_label": claim.version_label,
                "source_timestamp": claim.source_timestamp,
                "uploaded_at": claim.uploaded_at,
                "dated": claim.source_timestamp is not None,
                # Undated sources sit where they were uploaded, and say so (UI_UX §3.6).
                "order_label": claim.source_timestamp
                or f"undated · uploaded {_ordinal(upload_rank[claim.claim_id])}",
                "raw_value": claim.raw_value,
                "normalized_value": claim.normalized_value,
                "unit": claim.unit,
                "quote": claim.quote,
                "source_chunk_id": claim.source_chunk_id,
                "changed": previous is not None
                and (claim.normalized_value, claim.unit)
                != (previous.normalized_value, previous.unit),
                "conflict_ids": conflicts,
                "selected": selection.selected is not None
                and claim.claim_id == selection.selected.claim_id,
            }
        )
        previous = claim
    subject, attribute = key.split("/", 1)
    return {
        "key": key,
        "subject": subject,
        "attribute": attribute,
        "label": PLAIN_KEY.get(key, key),
        "type": KEYS[key].value_type,
        "selection_rule": selection.rule,
        "selected_claim_id": selection.selected.claim_id if selection.selected else None,
        "events": events,
    }
