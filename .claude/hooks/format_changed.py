#!/usr/bin/env python3
"""PostToolUse hook: format the one file that just changed, if a formatter is installed.

Formats only the edited file, so it stays fast on every edit. Before M1 there is no formatter and
this does nothing. It never blocks: formatting is a convenience, and the Stop gate plus CI are where
failures count.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PRETTIER_SUFFIXES = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".css",
    ".json",
    ".md",
    ".yml",
    ".yaml",
}


def ruff_command() -> list[str] | None:
    """`ruff` from PATH, or `python -m ruff` when it was pip-installed without Scripts on PATH."""
    found = shutil.which("ruff")
    if found:
        return [found]
    if importlib.util.find_spec("ruff") is not None:
        return [sys.executable, "-m", "ruff"]
    return None


def find_prettier(start: Path, root: Path) -> Path | None:
    for directory in [start, *start.parents]:
        for name in ("prettier.cmd", "prettier"):
            candidate = directory / "node_modules" / ".bin" / name
            if candidate.exists():
                return candidate
        if directory == root:
            break
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    raw = (payload.get("tool_input") or {}).get("file_path")
    if not raw:
        return 0

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()).resolve()
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        return 0

    command: list[str] | None = None
    ruff = ruff_command() if path.suffix == ".py" else None
    if ruff:
        command = [*ruff, "format", "--quiet", str(path)]
    elif path.suffix in PRETTIER_SUFFIXES:
        prettier = find_prettier(path.parent, root)
        if prettier:
            command = [str(prettier), "--write", "--log-level", "warn", str(path)]

    if command:
        try:
            subprocess.run(command, cwd=root, capture_output=True, timeout=25, check=False)
        except (OSError, subprocess.SubprocessError):
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
