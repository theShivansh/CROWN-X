#!/usr/bin/env python3
"""Check that the Claude Code harness is wired correctly. Runs in CI and before each milestone.

    python scripts/validate_kit.py

Checks: required files exist; settings and MCP JSON parse; every hook script referenced exists;
agents and skills have valid frontmatter; CLAUDE.md stays under its size limit; paths named in the
docs exist; no credential pattern appears in tracked text files. Exit 1 on any error.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD_MAX_LINES = 120
DESCRIPTION_MAX = 1536

REQUIRED = [
    "CLAUDE.md",
    "README.md",
    "CREDITS.md",
    ".mcp.json",
    ".gitignore",
    ".claude/settings.json",
    "docs/PROGRESS.md",
    "docs/DECISIONS.md",
    "docs/MILESTONES.md",
    "docs/HACKATHON.md",
    "docs/PRD.md",
    "docs/SRS.md",
    "docs/ARCHITECTURE.md",
    "docs/UI_UX.md",
    "docs/DESIGN.md",
    "docs/EVALUATION.md",
    "docs/SECURITY.md",
    "docs/BENCHMARKS.md",
    "prompts/README.md",
    "prompts/00-OPENING-BOOTSTRAP.md",
    "prompts/01-M1-WALKING-SKELETON.md",
    "prompts/02-M2-GROUNDED-ANSWERS.md",
    "prompts/03-M3-CONTRADICTIONS.md",
    "prompts/04-M4-TIMELINE-POLISH-RELIABILITY.md",
    "prompts/05-M5-WORKFLOW-LEARNING-LITE.md",
    "prompts/06-M6-FREEZE-AND-SUBMIT.md",
    "prompts/07-UI-SCREEN-PASS.md",
    "prompts/08-TRIAGE-BEHIND-SCHEDULE.md",
]

#: Paths the docs mention that are created later, by a milestone or a script.
CREATED_LATER = {
    "docs/WRITEUP.md",
    "docs/VIDEO_TAKE_SHEET.md",
    "docs/BLOG_DRAFT.md",
    "docs/decisions/archive.md",
    ".claude/skills/THIRD_PARTY_SKILLS.md",
    ".claude/skills/ui-ux-pro-max/scripts/search.py",
    ".claude/skills/design-taste-frontend/",
    ".claude/skills/ui-ux-pro-max/",
    ".claude/skills/verify/SKILL.md",
    ".github/",
}

TEXT_SUFFIXES = {
    ".md",
    ".json",
    ".py",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
    ".ts",
    ".tsx",
    ".js",
    ".css",
}
SKIP_DIRS = {".git", "node_modules", ".next", ".venv", "__pycache__", ".aws-sam"}
#: Installed third-party skills are scanned for secrets, but their own doc references aren't ours.
THIRD_PARTY_SKILLS = {"design-taste-frontend", "ui-ux-pro-max"}

errors: list[str] = []


def error(message: str) -> None:
    errors.append(message)


def frontmatter(path: Path) -> dict[str, str] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    fields: dict[str, str] = {}
    for line in text[3:end].splitlines():
        match = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip().strip('"')
    return fields


def check_required() -> None:
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            error(f"missing required file: {rel}")


def check_json_and_hooks() -> None:
    for rel in (".claude/settings.json", ".mcp.json"):
        path = ROOT / rel
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            error(f"{rel}: invalid JSON ({exc})")
            continue
        if rel != ".claude/settings.json":
            continue
        for event, groups in (data.get("hooks") or {}).items():
            for group in groups:
                for handler in group.get("hooks", []):
                    for part in [handler.get("command", ""), *handler.get("args", [])]:
                        if "${CLAUDE_PROJECT_DIR}" in part:
                            target = ROOT / part.replace("${CLAUDE_PROJECT_DIR}/", "")
                            if not target.exists():
                                error(f"settings.json {event}: hook script not found: {part}")


def check_agents() -> None:
    names: set[str] = set()
    for path in sorted((ROOT / ".claude" / "agents").glob("*.md")):
        fields = frontmatter(path)
        rel = path.relative_to(ROOT)
        if fields is None:
            error(f"{rel}: missing frontmatter")
            continue
        for key in ("name", "description"):
            if not fields.get(key):
                error(f"{rel}: frontmatter needs `{key}`")
        if "tools" not in fields and "disallowedTools" not in fields:
            error(f"{rel}: set `tools` or `disallowedTools` so the agent isn't granted everything")
        name = fields.get("name", "")
        if name in names:
            error(f"{rel}: duplicate agent name {name}")
        names.add(name)
        if name and name != path.stem:
            error(f"{rel}: name `{name}` differs from the file name")


def check_skills() -> None:
    for path in sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
        rel = path.relative_to(ROOT)
        fields = frontmatter(path)
        if fields is None or not fields.get("description"):
            error(f"{rel}: frontmatter needs a `description`")
            continue
        length = len(fields.get("description", "")) + len(fields.get("when_to_use", ""))
        if length > DESCRIPTION_MAX:
            error(f"{rel}: description + when_to_use is {length} chars (limit {DESCRIPTION_MAX})")


def check_claude_md() -> None:
    path = ROOT / "CLAUDE.md"
    if path.exists():
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > CLAUDE_MD_MAX_LINES:
            error(
                f"CLAUDE.md is {lines} lines (limit {CLAUDE_MD_MAX_LINES}); move detail to docs or skills"
            )


def our_docs() -> list[Path]:
    paths = [
        ROOT / "CLAUDE.md",
        ROOT / "README.md",
        *sorted((ROOT / "docs").glob("*.md")),
        *sorted((ROOT / "prompts").glob("*.md")),
    ]
    for path in sorted((ROOT / ".claude").rglob("*.md")):
        parts = path.relative_to(ROOT / ".claude").parts
        if len(parts) > 1 and parts[0] == "skills" and parts[1] in THIRD_PARTY_SKILLS:
            continue
        paths.append(path)
    return [p for p in paths if p.exists()]


def check_references() -> None:
    pattern = re.compile(r"`((?:docs|\.claude|scripts|tests|\.github|prompts)/[^`\s]+?)`")
    for path in our_docs():
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            ref = match.group(1).rstrip(".,:;)")
            if any(ch in ref for ch in "<>*$") or ref in CREATED_LATER:
                continue
            if not (ROOT / ref).exists():
                error(f"{path.relative_to(ROOT)}: references `{ref}`, which doesn't exist")


def check_secrets() -> None:
    guard = ROOT / ".claude" / "hooks" / "guard_secrets.py"
    if not guard.exists():
        return
    spec = importlib.util.spec_from_file_location("guard_secrets", guard)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    patterns = {label: re.compile(p) for label, p in module.PATTERNS.items()}

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, regex in patterns.items():
            if regex.search(text):
                error(f"{path.relative_to(ROOT)}: contains a {label} pattern")


def main() -> int:
    check_required()
    check_json_and_hooks()
    check_agents()
    check_skills()
    check_claude_md()
    check_references()
    check_secrets()

    if errors:
        print(f"Kit validation failed ({len(errors)}):")
        for message in errors:
            print(f"  - {message}")
        return 1
    agents = len(list((ROOT / ".claude" / "agents").glob("*.md")))
    skills = len(list((ROOT / ".claude" / "skills").glob("*/SKILL.md")))
    print(f"Kit valid: {agents} agents, {skills} skills, hooks wired, no credential patterns.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
