"""The contradiction predicate (ADR-003): deterministic code, never a model, decides that two claims
conflict. Pure; conflicts are derived from the stored claims whenever they're read (ADR-020), so they
can't go stale and their IDs are stable.

Two claims conflict when all of these hold:
- the same canonical key (subject and attribute) and the same value type;
- both normalized (an ambiguous or unparsed value never conflicts);
- the same unit (different units are incomparable, not conflicting);
- from different documents;
- different normalized values.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations

from crownx.domain.claims import Claim
from crownx.domain.selection import Selection, select
from crownx.domain.vocabulary import CRITICAL_ATTRIBUTES, PLAIN_KEY


@dataclass(frozen=True)
class ConflictPair:
    conflict_id: str
    older: Claim  # by the key's selection order
    newer: Claim


@dataclass(frozen=True)
class ConflictGroup:
    key: str
    subject: str
    attribute: str
    value_type: str
    severity: str
    selection: Selection
    pairs: tuple[ConflictPair, ...]

    @property
    def primary(self) -> ConflictPair:
        """The pair the inspector opens on: the newest stale value against the first source that
        carried the current one (SCENARIO §8: brief v1 against the organiser update)."""
        chosen = self.selection.selected
        if chosen is None:
            return self.pairs[0]
        ordered = self.selection.ordered
        stale = [i for i, c in enumerate(ordered) if c.normalized_value != chosen.normalized_value]
        if not stale:
            return self.pairs[0]
        left = ordered[stale[-1]]
        right = next(
            c for c in ordered[stale[-1] + 1 :] if c.normalized_value == chosen.normalized_value
        )
        return next(p for p in self.pairs if {p.older.claim_id, p.newer.claim_id} == {
            left.claim_id, right.claim_id
        })  # fmt: skip


def conflict_id(a: Claim, b: Claim) -> str:
    first, second = sorted((a.claim_id, b.claim_id))
    return "cf_" + hashlib.sha256(f"{first}|{second}".encode()).hexdigest()[:20]


def conflicts_between(a: Claim, b: Claim) -> bool:
    return (
        a.key == b.key
        and a.value_type == b.value_type
        and a.comparable
        and b.comparable
        and a.unit == b.unit
        and a.document_id != b.document_id
        and a.normalized_value != b.normalized_value
    )


def detect(claims: Iterable[Claim]) -> list[ConflictGroup]:
    by_key: dict[str, list[Claim]] = defaultdict(list)
    for claim in _one_per_document_value(claims):
        if claim.comparable:
            by_key[claim.key].append(claim)
    groups = []
    for key in sorted(by_key):
        members = by_key[key]
        selection = select(members)
        position = {c.claim_id: i for i, c in enumerate(selection.ordered)}
        pairs = []
        for a, b in combinations(members, 2):
            if conflicts_between(a, b):
                older, newer = sorted((a, b), key=lambda c: position[c.claim_id])
                pairs.append(ConflictPair(conflict_id(a, b), older, newer))
        if not pairs:
            continue
        first = members[0]
        groups.append(
            ConflictGroup(
                key=key,
                subject=first.subject,
                attribute=first.attribute,
                value_type=first.value_type,
                severity="high"
                if first.attribute in CRITICAL_ATTRIBUTES and first.value_type in ("date", "number")
                else "medium",
                selection=selection,
                pairs=tuple(sorted(pairs, key=lambda p: p.conflict_id)),
            )
        )
    return groups


def _one_per_document_value(claims: Iterable[Claim]) -> list[Claim]:
    """A document that states one value twice is one source for it (chunk overlap, a summary)."""
    kept: dict[tuple[str, str, str | None, str | None], Claim] = {}
    for claim in sorted(claims, key=lambda c: (c.document_id, c.value_start)):
        slot = (claim.document_id, claim.key, claim.normalized_value, claim.unit)
        if claim.normalized_value is None:
            slot = (claim.document_id, claim.key, claim.claim_id, None)
        kept.setdefault(slot, claim)
    return list(kept.values())


def claim_view(claim: Claim) -> dict:
    """A claim as the API returns it: everything but the workspace, which the path already names."""
    return claim.model_dump(exclude={"workspace_id"})


def group_view(group: ConflictGroup) -> dict:
    """The `/conflicts` and `/query` shape (SRS §4, ADR-020). Built from data only; the UI renders
    it without reading any answer text."""
    selected = group.selection.selected
    return {
        "key": group.key,
        "subject": group.subject,
        "attribute": group.attribute,
        "label": PLAIN_KEY.get(group.key, group.key.replace("/", " ").replace("_", " ")),
        "type": group.value_type,
        "severity": group.severity,
        "selection_rule": group.selection.rule,
        "selected_claim_id": selected.claim_id if selected else None,
        "selected_value": selected.normalized_value if selected else None,
        "selected_unit": selected.unit if selected else None,
        # Every claim on the key, oldest first by the rule: the inspector's timeline.
        "claims": [claim_view(c) for c in group.selection.ordered],
        "pairs": [
            {
                "conflict_id": p.conflict_id,
                "claim_a": p.older.claim_id,
                "claim_b": p.newer.claim_id,
                "type": group.value_type,
                "severity": group.severity,
                "status": "open",
            }
            for p in group.pairs
        ],
        "primary_conflict_id": group.primary.conflict_id,
    }


def audit_record(view: dict) -> list[dict]:
    """What the audit record and the logs keep per conflict, from a `group_view`: IDs, extraction
    confidence and the selection rule (ADR-020). No document text."""
    confidence = {
        c["claim_id"]: (c.get("confidence") or {}).get("extraction") for c in view["claims"]
    }
    return [
        {
            "conflict_id": pair["conflict_id"],
            "key": view["key"],
            "claim_ids": [pair["claim_a"], pair["claim_b"]],
            "extraction_confidence": [
                confidence.get(pair["claim_a"]),
                confidence.get(pair["claim_b"]),
            ],
            "selected_claim_id": view["selected_claim_id"],
            "selection_rule": view["selection_rule"],
        }
        for pair in view["pairs"]
    ]
