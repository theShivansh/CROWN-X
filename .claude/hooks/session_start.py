#!/usr/bin/env python3
"""SessionStart hook: start every session from the ledger, not from memory.

A SessionStart hook's stdout is added to Claude's context. This prints the "Next session starts here"
line from docs/PROGRESS.md, the branch, and the uncommitted files, so a fresh, resumed or compacted
session knows where the work stands before it does anything.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def git(root: Path, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def main() -> int:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        pass

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    lines: list[str] = []

    progress = root / "docs" / "PROGRESS.md"
    if progress.exists():
        for line in progress.read_text(encoding="utf-8").splitlines():
            if line.lower().lstrip("#* ").startswith("next session starts here"):
                lines.append(line.strip().lstrip("#* ").strip())
                break

    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        dirty = [entry for entry in git(root, "status", "--porcelain").splitlines() if entry]
        lines.append(f"Branch {branch}, {len(dirty)} uncommitted file(s).")
        lines.extend(f"  {entry}" for entry in dirty[:15])
        if len(dirty) > 15:
            lines.append(f"  ... and {len(dirty) - 15} more")

    if lines:
        print("Project state from .claude/hooks/session_start.py:")
        print("\n".join(lines))
        print("Run /resume before starting milestone work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
