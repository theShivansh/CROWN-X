"""Deterministic value normalization for claims (ADR-003). A value that can't be normalized without a
guess stays unnormalized (`value is None`), and an unnormalized claim can never conflict.

- Dates: explicit formats with month names, ISO `YYYY-MM-DD`, or an all-numeric date. A missing year
  comes only from the document's own `source_timestamp`. An all-numeric date whose day and month are
  both 12 or less (`09/10/2026`) is ambiguous and stays unnormalized.
- Numbers: `Decimal` plus a canonical unit from the table below. Different units are incomparable.
- Owners: casefold, honorifics stripped, whitespace collapsed.

`certainty` is the value's half of a claim's extraction confidence (ADR-020): 1.0 for a fully explicit
value, 0.9 when the year was inferred from the document's date, 0.0 when unnormalized.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?"
    r"|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip

# One pattern for finding a date in text; `normalize_date` then reads the match's groups.
DATE = re.compile(
    rf"(?P<iso>\b\d{{4}}-\d{{2}}-\d{{2}}\b)"
    rf"|(?P<dmy>\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH}\b\.?(?:,?\s+\d{{4}}\b)?)"
    rf"|(?P<mdy>\b{MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\b(?:,?\s+\d{{4}}\b)?)"
    rf"|(?P<numeric>\b\d{{1,2}}[/.]\d{{1,2}}[/.]\d{{4}}\b)",
    re.IGNORECASE,
)

# Canonical units. Anything not listed can't be compared with anything else.
UNITS = {
    "₹": "INR",
    "inr": "INR",
    "rs": "INR",
    "rs.": "INR",
    "rupees": "INR",
    "requests per minute": "requests_per_minute",
    "requests/minute": "requests_per_minute",
    "req/min": "requests_per_minute",
    "rpm": "requests_per_minute",
    "requests per second": "requests_per_second",
    "req/s": "requests_per_second",
    "rps": "requests_per_second",
    "mb": "MB",
    "kb": "KB",
    "%": "percent",
    "percent": "percent",
}
_CURRENCY = r"(?:₹|INR|Rs\.?)"
_AMOUNT = r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?"
MONEY = re.compile(
    rf"(?:{_CURRENCY}\s*(?P<a1>{_AMOUNT}))|(?:(?P<a2>{_AMOUNT})\s*(?:rupees|INR)\b)",
    re.IGNORECASE,
)
RATE = re.compile(
    rf"(?P<amount>{_AMOUNT})\s*(?P<unit>requests per minute|requests/minute|req/min|rpm"
    r"|requests per second|req/s|rps)\b",
    re.IGNORECASE,
)
_HONORIFIC = re.compile(r"^(?:prof|dr|mr|mrs|ms|shri|smt)\.?\s+", re.IGNORECASE)
PERSON = re.compile(
    r"(?:(?:Prof|Dr|Mr|Mrs|Ms)\.?[ \t]+)?[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+){1,2}",
)


@dataclass(frozen=True)
class Normalized:
    value: str | None  # ISO date, Decimal as text, or a normalized name; None when not normalized
    unit: str | None
    certainty: float


UNNORMALIZED = Normalized(value=None, unit=None, certainty=0.0)


def normalize_date(raw: str, document_date: str | None) -> Normalized:
    match = DATE.fullmatch(raw.strip().rstrip("."))
    if match is None:
        return UNNORMALIZED
    text = match.group(0)
    if match.group("iso"):
        year, month, day = (int(p) for p in text.split("-"))
        return _dated(year, month, day, 1.0)
    if match.group("numeric"):
        first, second, year = (int(p) for p in re.split(r"[/.]", text))
        if first <= 12 and second <= 12 and first != second:
            return UNNORMALIZED  # day-month order unknown: never guessed
        day, month = (first, second) if first > 12 or first == second else (second, first)
        return _dated(year, month, day, 1.0)
    month_name = re.search(MONTH, text, re.IGNORECASE)
    numbers = [int(n) for n in re.findall(r"\d+", text)]
    assert month_name is not None
    month = _MONTHS[month_name.group(0)[:3].lower()]
    day = numbers[0]
    if len(numbers) == 2:
        return _dated(numbers[1], month, day, 1.0)
    if document_date is None:
        return UNNORMALIZED  # no year and no document date to take it from
    return _dated(int(document_date[:4]), month, day, 0.9)


def normalize_money(raw: str) -> Normalized:
    match = MONEY.fullmatch(raw.strip())
    if match is None:
        return UNNORMALIZED
    return _number(match.group("a1") or match.group("a2"), "INR")


def normalize_rate(raw: str) -> Normalized:
    match = RATE.fullmatch(raw.strip())
    if match is None:
        return UNNORMALIZED
    return _number(match.group("amount"), UNITS[match.group("unit").lower()])


def normalize_owner(raw: str) -> Normalized:
    name = " ".join(_HONORIFIC.sub("", raw.strip()).split()).casefold()
    return Normalized(value=name, unit=None, certainty=1.0) if name else UNNORMALIZED


def _number(amount: str, unit: str) -> Normalized:
    try:
        value = Decimal(amount.replace(",", ""))
    except InvalidOperation:
        return UNNORMALIZED
    # Canonical text: no exponent, no trailing zeros, so 60 and 60.0 compare equal.
    text = format(value.normalize(), "f")
    return Normalized(value=text, unit=unit, certainty=1.0)


def _dated(year: int, month: int, day: int, certainty: float) -> Normalized:
    try:
        return Normalized(date(year, month, day).isoformat(), None, certainty)
    except ValueError:
        return UNNORMALIZED
