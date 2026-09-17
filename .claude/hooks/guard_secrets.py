#!/usr/bin/env python3
"""PreToolUse hook for file edits: never write a credential into the project.

Two checks:
1. The target is an env file (`.env`, `.env.local`, ...). Claude never writes those. `.env.example`
   is allowed, and its content is still scanned.
2. The new content matches a live-credential pattern. The patterns are specific on purpose: a generic
   "looks random" rule blocks hashes and test fixtures, and a guard people learn to override is worse
   than none.

A match returns a deny decision with the credential *type*, never the matched text.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import PurePath

PATTERNS: dict[str, str] = {
    "AWS access key ID": r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    "AWS secret access key": r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}\b",
    "private key": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP |ENCRYPTED )?PRIVATE KEY-----",
    "Anthropic API key": r"\bsk-ant-[A-Za-z0-9_-]{20,}",
    "OpenAI-style API key": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}",
    "Groq API key": r"\bgsk_[A-Za-z0-9]{20,}",
    "GitHub token": r"\b(?:ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{50,}",
    "Slack token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    "Google API key": r"\bAIza[0-9A-Za-z_-]{35}\b",
}

ENV_FILE = re.compile(r"^\.env(?:\..+)?$")


def texts(tool_input: dict) -> list[str]:
    found = [
        str(tool_input.get(key, ""))
        for key in ("content", "new_string", "new_source")
        if tool_input.get(key)
    ]
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and edit.get("new_string"):
            found.append(str(edit["new_string"]))
    return found


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"CROWN-X secret guard: {reason}",
                }
            }
        )
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool_input = payload.get("tool_input") or {}

    path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
    name = PurePath(path.replace("\\", "/")).name if path else ""
    if name and ENV_FILE.match(name) and name != ".env.example":
        deny(
            f"{name} holds real credentials, and Claude doesn't write it. Put the variable name "
            "in docs/ARCHITECTURE.md (Configuration) and set the value yourself."
        )
        return 0

    for text in texts(tool_input):
        for label, pattern in PATTERNS.items():
            if re.search(pattern, text):
                deny(
                    f"the new content contains what looks like a {label}. Read it from the "
                    "environment or AWS instead; if this is a documented fake, split the literal."
                )
                return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
