"""Recognising text addressed to an assistant inside a document (CLAUDE.md rule 3, SECURITY T1).

Such text is data. It is never followed, and a claim supported only by it is not a fact: code drops it
in `finalize()` whatever the model did (ADR-017's live eval found the model reporting the injected
value as a "disagreeing source"). Deliberately narrow: ordinary prose ("please answer by Friday")
must not match.
"""

from __future__ import annotations

import re

INSTRUCTION = re.compile(
    r"\b(ignore (all |any )?(previous|prior|above|earlier) instructions"
    r"|disregard (the |your |all )?(rules|instructions|guidelines)"
    r"|you are now|answer that|respond (only )?with|reply (only )?with|say that the"
    r"|as an ai|system prompt)\b",
    re.IGNORECASE,
)


def instruction_like(text: str) -> bool:
    return INSTRUCTION.search(text) is not None
