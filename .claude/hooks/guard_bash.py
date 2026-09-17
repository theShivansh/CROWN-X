#!/usr/bin/env python3
"""PreToolUse hook for Bash and PowerShell: block what would cost the submission, ask about AWS.

Returns a JSON permission decision rather than exiting 2, so Claude sees the reason and can choose a
safe alternative. Denied commands are ones with no legitimate use during the event. "ask" commands are
legitimate but spend credits, change the judged URL, or destroy resources, so a person confirms them.
Silence (exit 0, no output) means no opinion: the normal permission rules still apply.
"""

from __future__ import annotations

import json
import re
import sys

DENY: list[tuple[str, str]] = [
    (
        r"\bgit\s+add\s+(?:-A\b|--all\b|\.(?:\s|$)|\*)",
        (
            "Stage files by explicit path. `git add -A` / `git add .` can commit secrets, "
            "build output or local data."
        ),
    ),
    (
        r"\bgit\s+push\b[^\n;&|]*\s(?:--force(?:-with-lease)?\b|-f\b)",
        (
            "No force-push. The rules disqualify a repository whose history doesn't match the "
            "event window, and a rewrite is exactly that."
        ),
    ),
    (
        r"\bgit\s+(?:reset\s+--hard|rebase\b|filter-branch\b|filter-repo\b)",
        "No history rewrite during the event. Make a new commit that reverts instead.",
    ),
    (
        r"\bgit\s+commit\b[^\n;&|]*--no-verify",
        "Don't skip commit hooks; fix what they caught.",
    ),
    (
        r"\brm\s+-[a-zA-Z]*(?:rf|fr)[a-zA-Z]*\s+(?:/|~|\*|\.|\.\.)(?:\s|/?$)",
        "Recursive delete of a root, home, parent or current directory.",
    ),
    (
        r"Remove-Item\b[^\n;|]*-Recurse[^\n;|]*\s(?:[A-Za-z]:\\?|~|\.|\*)(?:\s|$)",
        "Recursive delete of a drive root, home or current directory.",
    ),
]

ASK: list[tuple[str, str]] = [
    (
        r"\b(?:sam|cdk)\s+(?:delete|destroy)\b|\bterraform\s+destroy\b",
        "Destroys AWS resources.",
    ),
    (
        r"\baws\s+[\w-]+\s+(?:delete-[\w-]+|remove-[\w-]+|terminate-[\w-]+|rm\b|rb\b)",
        "Deletes AWS resources or data.",
    ),
    (
        r"\bsam\s+deploy\b|\bamplify\s+publish\b",
        "Deploys to AWS: spends credits and changes the judged URL.",
    ),
]


def decision(kind: str, reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": kind,
                    "permissionDecisionReason": f"CROWN-X guard: {reason}",
                }
            }
        )
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = str((payload.get("tool_input") or {}).get("command", ""))
    if not command:
        return 0

    for pattern, reason in DENY:
        if re.search(pattern, command, flags=re.IGNORECASE):
            decision("deny", reason)
            return 0
    for pattern, reason in ASK:
        if re.search(pattern, command, flags=re.IGNORECASE):
            decision("ask", reason)
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
