#!/usr/bin/env python3
"""Stop hook: a turn that changed code does not end with lint or typecheck broken.

Checks only what the working tree changed:
- Python files: `ruff check` on those files, when ruff is installed.
- TypeScript files: the `typecheck` script of the nearest package.json that defines one.

A failure exits 2 with the tail of the output on stderr. For a Stop hook that keeps Claude working,
and Claude sees the reason. `stop_hook_active` is true when Claude is already continuing because of
this hook; then it exits 0, so a check Claude cannot fix can't trap the session in a loop. In that
case Claude must report the failure plainly (CLAUDE.md rule 6).

Full test suites don't run here; they belong to /verify-stage and CI. Set CROWN_SKIP_STOP_GATE=1 to
skip, for example while a milestone is mid-refactor on purpose.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TS_SUFFIXES = (".ts", ".tsx")


def ruff_command() -> list[str] | None:
    """`ruff` from PATH, or `python -m ruff` when it was pip-installed without Scripts on PATH."""
    found = shutil.which("ruff")
    if found:
        return [found]
    if importlib.util.find_spec("ruff") is not None:
        return [sys.executable, "-m", "ruff"]
    return None


def run(command: list[str], cwd: Path, timeout: int) -> tuple[bool, str]:
    try:
        done = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s: {' '.join(command)}"
    except OSError as error:
        return True, f"skipped ({error})"
    return done.returncode == 0, (done.stdout + done.stderr)[-2500:]


def changed_files(root: Path) -> list[Path]:
    names: set[str] = set()
    for args in (
        ["diff", "--name-only", "HEAD"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        ok, output = run(["git", *args], root, 10)
        if ok:
            names.update(line.strip() for line in output.splitlines() if line.strip())
    return [root / name for name in sorted(names) if (root / name).exists()]


def typecheck_dir(path: Path, root: Path) -> Path | None:
    for directory in [path.parent, *path.parent.parents]:
        manifest = directory / "package.json"
        if manifest.exists():
            try:
                scripts = json.loads(manifest.read_text(encoding="utf-8")).get("scripts", {})
            except (json.JSONDecodeError, OSError):
                scripts = {}
            if "typecheck" in scripts:
                return directory
        if directory == root:
            break
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if payload.get("stop_hook_active") or os.environ.get("CROWN_SKIP_STOP_GATE") == "1":
        return 0

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()).resolve()
    if not (root / ".git").exists():
        return 0
    files = changed_files(root)
    failures: list[str] = []

    python_files = [str(f) for f in files if f.suffix == ".py"]
    ruff = ruff_command()
    if python_files and ruff:
        ok, output = run([*ruff, "check", *python_files], root, 60)
        if not ok:
            failures.append(f"ruff check failed:\n{output}")

    runner = shutil.which("pnpm") or shutil.which("npm")
    packages = {d for f in files if f.suffix in TS_SUFFIXES and (d := typecheck_dir(f, root))}
    for package in sorted(packages):
        if not runner:
            break
        ok, output = run([runner, "run", "typecheck"], package, 150)
        if not ok:
            failures.append(f"typecheck failed in {package.relative_to(root) or '.'}:\n{output}")

    if failures:
        print(
            "CROWN-X stop gate: the working tree has failing checks. Fix them before ending the "
            "turn, or say plainly which check is still failing and why.\n\n"
            + "\n\n".join(failures),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
