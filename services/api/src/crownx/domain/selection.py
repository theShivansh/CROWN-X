"""Which value is current, and by which written rule (FR-08, ADR-003). Pure and deterministic.

Rules, first that applies wins:
1. `newest_source_timestamp`: every claim has the document's own date.
2. `version_order`: every claim comes from one document family (the file name without its version)
   and has a comparable version label: v1 < v1.1 < v2, draft < final.
3. `latest_upload`: every claim has an upload time. The weakest rule, and the UI says so.
4. No rule applies, or the two newest claims tie on the rule's key with different values: no
   selection. Values that disagree without an ordering signal are shown as disagreeing, never picked.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from crownx.domain.claims import Claim

NEWEST_SOURCE_TIMESTAMP = "newest_source_timestamp"
VERSION_ORDER = "version_order"
LATEST_UPLOAD = "latest_upload"

_VERSION_SUFFIX = re.compile(r"[-_ ]*(?:v\d+(?:\.\d+)*|draft|final)$", re.IGNORECASE)


@dataclass(frozen=True)
class Selection:
    rule: str | None
    ordered: tuple[Claim, ...]  # oldest first by the rule; by upload time when no rule applies
    selected: Claim | None


def select(claims: Sequence[Claim]) -> Selection:
    claims = list(claims)
    if not claims:
        return Selection(rule=None, ordered=(), selected=None)
    if all(c.source_timestamp for c in claims):
        return _by(claims, NEWEST_SOURCE_TIMESTAMP, lambda c: (c.source_timestamp or "",))
    versions = [version_key(c.version_label) for c in claims]
    if len({family(c.filename) for c in claims}) == 1 and all(v is not None for v in versions):
        rank = dict(zip((c.claim_id for c in claims), versions, strict=True))
        return _by(claims, VERSION_ORDER, lambda c: rank[c.claim_id] or ())
    if all(c.uploaded_at for c in claims):
        return _by(claims, LATEST_UPLOAD, lambda c: (c.uploaded_at,))
    return Selection(rule=None, ordered=tuple(_upload_order(claims)), selected=None)


def _by(claims: list[Claim], rule: str, key: Callable[[Claim], tuple]) -> Selection:
    ordered = sorted(claims, key=lambda c: (key(c), c.uploaded_at, c.value_start))
    newest = ordered[-1]
    tied = [c for c in ordered if key(c) == key(newest)]
    if len({c.normalized_value for c in tied}) > 1:
        return Selection(rule=None, ordered=tuple(ordered), selected=None)
    return Selection(rule=rule, ordered=tuple(ordered), selected=newest)


def _upload_order(claims: list[Claim]) -> list[Claim]:
    return sorted(claims, key=lambda c: (c.uploaded_at or "", c.value_start))


def family(filename: str) -> str:
    """`project-brief-v1.pdf` and `project-brief-v2.md` are one family: `project-brief`."""
    stem = filename.rsplit(".", 1)[0]
    return _VERSION_SUFFIX.sub("", stem).casefold()


def version_key(label: str | None) -> tuple[int, ...] | None:
    """v1 < v1.1 < v2; draft < final. Other labels ("update 3", "Sync 5") don't order versions."""
    if not label:
        return None
    text = label.strip().lower()
    if text == "draft":
        return (-1,)
    if text == "final":
        return (1_000_000,)
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", text)
    return tuple(int(p) for p in match.group(1).split(".")) if match else None
