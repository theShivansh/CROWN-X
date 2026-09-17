#!/usr/bin/env python3
"""Install the pinned third-party design skills into .claude/skills/.

    python scripts/install_ui_skills.py            # install, skipping skills already at the pinned commit
    python scripts/install_ui_skills.py --force    # reinstall

Why a script rather than `npx skills add` or the plugin marketplace: both install whatever is on the
default branch today. This fetches one exact commit per repository, copies only the skill directory
plus its licence, records what was installed, and applies the one documented patch. So what Claude
loads is what was reviewed (docs/DECISIONS.md ADR-007).

Needs git on PATH. No other dependencies.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"


@dataclass(frozen=True)
class Source:
    name: str
    repo: str
    sha: str
    subdir: str
    licence: str = "LICENSE"
    #: (old, new) text replacements in SKILL.md, each required to match at least once.
    patches: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    note: str = ""


SOURCES: tuple[Source, ...] = (
    Source(
        name="design-taste-frontend",
        repo="https://github.com/Leonxlnx/taste-skill.git",
        sha="ccbc15639c97057cbfcf32ecebc38ef716e4bb37",
        subdir="skills/taste-skill",
        note="Anti-slop frontend rules. Upstream scope: landing pages, portfolios, redesigns.",
    ),
    Source(
        name="ui-ux-pro-max",
        repo="https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git",
        sha="8bd29e775453ebcae52b6e6514fbf134df0c5770",
        subdir=".claude/skills/ui-ux-pro-max",
        patches=(
            (
                "${CLAUDE_PLUGIN_ROOT}/.claude/skills/ui-ux-pro-max/",
                "${CLAUDE_SKILL_DIR}/",
            ),
        ),
        note=(
            "Local UX/design search. Patched: script paths use ${CLAUDE_SKILL_DIR}, because "
            "${CLAUDE_PLUGIN_ROOT} only exists when installed as a plugin."
        ),
    ),
)

IGNORE = shutil.ignore_patterns("tests", "__pycache__", "*.pyc", ".git")


def git(*args: str, cwd: Path) -> None:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{done.stderr.strip()}")


def fetch(source: Source, workdir: Path) -> Path:
    checkout = workdir / source.name
    checkout.mkdir(parents=True)
    git("init", "--quiet", cwd=checkout)
    git("remote", "add", "origin", source.repo, cwd=checkout)
    git("fetch", "--quiet", "--depth", "1", "origin", source.sha, cwd=checkout)
    git("checkout", "--quiet", "FETCH_HEAD", cwd=checkout)
    return checkout


def install(source: Source, force: bool) -> str:
    dest = SKILLS / source.name
    marker = dest / ".pinned.json"
    if marker.exists() and not force:
        pinned = json.loads(marker.read_text(encoding="utf-8"))
        if pinned.get("sha") == source.sha:
            return f"{source.name}: already at {source.sha[:7]}, skipped"

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        checkout = fetch(source, Path(tmp))
        skill_dir = checkout / source.subdir
        if not (skill_dir / "SKILL.md").exists():
            raise RuntimeError(f"{source.name}: {source.subdir}/SKILL.md not found at {source.sha}")

        staged = Path(tmp) / f"{source.name}-staged"
        shutil.copytree(skill_dir, staged, ignore=IGNORE)
        licence = checkout / source.licence
        if licence.exists():
            shutil.copy2(licence, staged / "LICENSE")

        skill_md = staged / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        for old, new in source.patches:
            count = text.count(old)
            if count == 0:
                raise RuntimeError(
                    f"{source.name}: patch target not found; upstream changed. Review before pinning."
                )
            text = text.replace(old, new)
        skill_md.write_text(text, encoding="utf-8")

        (staged / ".pinned.json").write_text(
            json.dumps(
                {
                    "repo": source.repo,
                    "sha": source.sha,
                    "subdir": source.subdir,
                    "installed_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "patches": [list(p) for p in source.patches],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged, dest)
    return f"{source.name}: installed {source.sha[:7]} into {dest.relative_to(ROOT)}"


def write_manifest() -> None:
    lines = [
        "# Third-party skills",
        "",
        "Installed by `scripts/install_ui_skills.py` at pinned commits (ADR-007). Don't edit these",
        "directories by hand; change the pin in the script and reinstall with `--force`.",
        "",
        "| Skill | Repository | Commit | Licence | Note |",
        "|---|---|---|---|---|",
    ]
    for source in SOURCES:
        repo = source.repo.removeprefix("https://").removesuffix(".git")
        lines.append(f"| `{source.name}` | {repo} | `{source.sha}` | MIT | {source.note} |")
    (SKILLS / "THIRD_PARTY_SKILLS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="reinstall even if already pinned")
    args = parser.parse_args()

    if shutil.which("git") is None:
        print("git is required on PATH.", file=sys.stderr)
        return 1

    failed = False
    for source in SOURCES:
        try:
            print(install(source, args.force))
        except RuntimeError as error:
            failed = True
            print(f"FAILED {error}", file=sys.stderr)
    write_manifest()
    if not failed:
        print("Done. Skills are picked up by a running Claude Code session without a restart.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
