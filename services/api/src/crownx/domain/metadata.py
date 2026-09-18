"""Version label and source date from a document's header, deterministically (rag-evidence skill).

M3 picks the current value by `source_timestamp`, then `version_label`, then upload time, so a wrong
date here would put a stale value on screen. The rules are strict on purpose:
- only the header is read: the lines before the first blank line, at most five, so a date quoted in
  the body ("Deadline confirmed as 2026-09-22") is never taken for the document's own date;
- a date needs a day, a month name and a four-digit year, or an ISO `YYYY-MM-DD`; numeric forms like
  10/09/2026 are ambiguous (day-month order) and are ignored;
- two different dates in the header, or an impossible date, give None. Nothing is ever guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

HEADER_LINES = 5

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_MONTH = (
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?"
    r"|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DAY_MONTH_YEAR = re.compile(rf"\b(\d{{1,2}})\s+{_MONTH}\.?,?\s+(\d{{4}})\b", re.IGNORECASE)
_MONTH_DAY_YEAR = re.compile(rf"\b{_MONTH}\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.IGNORECASE)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

# First match wins, in this order; the label keeps the document's own wording.
_VERSIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bVersion:?\s*v?(\d+(?:\.\d+)*)\b", re.IGNORECASE), "v{}"),
    (re.compile(r"\bv(\d+(?:\.\d+)*)\b"), "v{}"),
    (re.compile(r"\bupdate\s+(\d+)\b", re.IGNORECASE), "update {}"),
    (re.compile(r"\bSync\s+(\d+)\b", re.IGNORECASE), "Sync {}"),
    (re.compile(r"\b(draft|final)\b", re.IGNORECASE), "{}"),
]


@dataclass(frozen=True)
class DocumentMetadata:
    version_label: str | None
    source_timestamp: str | None  # ISO date, e.g. "2026-09-10"


def header_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.lstrip().splitlines():
        if not line.strip():
            break
        lines.append(line.strip())
        if len(lines) == HEADER_LINES:
            break
    return lines


def extract_metadata(text: str) -> DocumentMetadata:
    header = header_lines(text)
    return DocumentMetadata(version_label=_version(header), source_timestamp=_source_date(header))


def _version(header: list[str]) -> str | None:
    for pattern, template in _VERSIONS:
        for line in header:
            match = pattern.search(line)
            if match:
                value = match.group(1)
                return template.format(value.lower() if template == "{}" else value)
    return None


def _source_date(header: list[str]) -> str | None:
    found: set[date] = set()
    for line in header:
        for match in _DAY_MONTH_YEAR.finditer(line):
            found.add(_valid(int(match.group(3)), _month(match.group(2)), int(match.group(1))))
        for match in _MONTH_DAY_YEAR.finditer(line):
            found.add(_valid(int(match.group(3)), _month(match.group(1)), int(match.group(2))))
        for match in _ISO.finditer(line):
            found.add(_valid(int(match.group(1)), int(match.group(2)), int(match.group(3))))
    if len(found) != 1 or None in found:
        return None  # no date, two different dates, or an impossible one: don't guess
    return next(iter(found)).isoformat()  # type: ignore[union-attr]


def _month(name: str) -> int:
    return _MONTHS[name[:3].lower()]


def _valid(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
