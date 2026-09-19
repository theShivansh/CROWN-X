"""The explicit vocabulary claims are extracted with (ADR-003, ADR-020, demo/SCENARIO.md §11).

Each canonical key lists its trigger phrases and the kind of value that must follow the trigger in the
same sentence. Only mapped wording becomes a claim: unmapped text is never guessed into a key, and a
key is only ever compared with the identical key. A trigger marked `label` is written as "Label: value"
and is the strongest evidence that the value belongs to the key.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from crownx.domain.normalize import DATE, MONEY, PERSON, RATE

ValueType = Literal["date", "number", "owner"]


@dataclass(frozen=True)
class Trigger:
    pattern: re.Pattern[str]
    label: bool = False  # "Budget cap: ₹50,000": the value is the label's own


@dataclass(frozen=True)
class KeySpec:
    subject: str
    attribute: str
    value_type: ValueType
    value: re.Pattern[str]  # what a value looks like for this key
    triggers: tuple[Trigger, ...]
    # A question is about this key only if it matches this (ADR-020). A retrieved chunk often holds
    # several facts, so a conflict joins a query only when its chunk was retrieved AND the question
    # names its fact: "Who is the faculty coordinator?" never shows the deadline conflict.
    asks: re.Pattern[str]
    # The sentence must also name this, for keys whose trigger is a common word ("limit").
    requires: re.Pattern[str] | None = None

    @property
    def key(self) -> str:
        return f"{self.subject}/{self.attribute}"


def _t(pattern: str, label: bool = False) -> Trigger:
    return Trigger(re.compile(pattern, re.IGNORECASE), label)


def _asks(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


VOCABULARY: tuple[KeySpec, ...] = (
    KeySpec(
        "submission",
        "deadline",
        "date",
        DATE,
        (
            _t(r"\bsubmissions?\s+(?:now\s+)?close\b"),
            _t(r"\bsubmission\s+deadline\b"),
            _t(r"\bdeadline\s+confirmed\s+as\b"),
            _t(r"\bsubmission\s+deadline\s*:", label=True),
        ),
        asks=_asks(r"\b(?:deadline|due date|submissions?|submit)\b"),
    ),
    KeySpec(
        "events_portal_api",
        "rate_limit",
        "number",
        RATE,
        (
            _t(r"\brate\s+limit\s*:", label=True),
            _t(r"\brate\s+limit\b"),
            _t(r"\blimited\b"),
            _t(r"\blimit\s+is\s+now\b"),
        ),
        asks=_asks(
            r"\b(?:rate[- ]?limits?|limit\w*|rpm|requests per minute|throttl\w*|restriction\w*)\b"
        ),
        requires=re.compile(r"\bportal\b", re.IGNORECASE),
    ),
    KeySpec(
        "budget",
        "cap",
        "number",
        MONEY,
        (
            _t(r"\bbudget\s+cap\s*:", label=True),
            _t(r"\brevised\s+cap\s*:", label=True),
            _t(r"\bbudget\s+cap\b"),
        ),
        # Not bare "budget": "How much is budgeted for printing?" asks about a line item.
        asks=_asks(r"\b(?:budget cap|cap|total budget|overall budget|grant)\b"),
    ),
    KeySpec(
        "deployment",
        "owner",
        "owner",
        PERSON,
        (
            _t(r"\bdeployment\s+owner\s*:", label=True),
            _t(r"\bdeployment\s+and\s+AWS\s+account\s*:", label=True),
        ),
        asks=_asks(r"\b(?:deploy\w*|release to production|aws account)\b"),
    ),
    # Kept apart on purpose (SCENARIO §5): a date one day from the deadline, for another event.
    KeySpec(
        "robotics_expo",
        "entries_close",
        "date",
        DATE,
        (_t(r"\bexpo\s+entries\s+close\b"),),
        asks=_asks(r"\b(?:expo|robotics)\b"),
    ),
)

_BY_KEY = {spec.key: spec for spec in VOCABULARY}


def asks_about(key: str, question: str) -> bool:
    spec = _BY_KEY.get(key)
    return bool(spec and spec.asks.search(question))


# Dates and numbers on these attributes are high severity; everything else is medium.
CRITICAL_ATTRIBUTES = frozenset({"deadline", "cap", "rate_limit"})

PLAIN_KEY = {
    "submission/deadline": "submission deadline",
    "events_portal_api/rate_limit": "Events Portal API rate limit",
    "budget/cap": "budget cap",
    "deployment/owner": "deployment owner",
    "robotics_expo/entries_close": "Robotics Expo entries close",
}
