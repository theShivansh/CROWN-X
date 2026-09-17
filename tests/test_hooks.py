"""The hooks decide things, so they are tested like code.

Each hook runs as Claude Code runs it: a subprocess with the event JSON on stdin and
CLAUDE_PROJECT_DIR set. Credential-shaped strings are assembled from pieces so this file never trips
the secret scanners it tests.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".claude" / "hooks"


def run_hook(name: str, payload: dict, project_dir: Path = ROOT) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)}
    env.pop("CROWN_SKIP_STOP_GATE", None)
    return subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )


def decision_of(done: subprocess.CompletedProcess) -> str | None:
    if not done.stdout.strip():
        return None
    return json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"]


def bash(command: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


# --- guard_bash ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git add -A",
        "git add .",
        "git add --all",
        "git push --force origin main",
        "git push -f",
        "git push --force-with-lease",
        "git reset --hard HEAD~1",
        "git rebase -i HEAD~3",
        'git commit --no-verify -m "wip"',
        "rm -rf /",
        "rm -rf .",
        "rm -fr ~",
    ],
)
def test_commands_that_cost_the_submission_are_denied(command):
    assert decision_of(run_hook("guard_bash.py", bash(command))) == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "sam deploy --guided",
        "sam delete --stack-name crown-x",
        "aws s3 rm s3://crown-x-docs --recursive",
        "aws dynamodb delete-table --table-name crown",
        "terraform destroy",
    ],
)
def test_aws_changes_ask_a_person(command):
    assert decision_of(run_hook("guard_bash.py", bash(command))) == "ask"


@pytest.mark.parametrize(
    "command",
    [
        "git add apps/web/src/app/page.tsx docs/PROGRESS.md",
        "git push origin main",
        "git status",
        "rm -rf apps/web/.next",
        "pnpm run typecheck",
        "aws sts get-caller-identity",
        "sam build",
    ],
)
def test_ordinary_commands_get_no_opinion(command):
    done = run_hook("guard_bash.py", bash(command))
    assert done.returncode == 0
    assert decision_of(done) is None


def test_powershell_recursive_delete_of_a_drive_is_denied():
    payload = {
        "tool_name": "PowerShell",
        "tool_input": {"command": "Remove-Item -Recurse -Force C:\\"},
    }
    assert decision_of(run_hook("guard_bash.py", payload)) == "deny"


# --- guard_secrets -----------------------------------------------------------------------------

FAKE = {
    "aws": "AKIA" + "Q" * 16,
    "anthropic": "sk-" + "ant-" + "a1" * 15,
    "groq": "gsk" + "_" + "b2" * 15,
    "github": "ghp" + "_" + "c" * 36,
    "private_key": "-----BEGIN " + "RSA PRIVATE KEY-----",
}


def write(path: str, content: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


@pytest.mark.parametrize("kind", sorted(FAKE))
def test_credentials_are_never_written(kind):
    done = run_hook("guard_secrets.py", write("apps/api/config.py", f'KEY = "{FAKE[kind]}"\n'))
    assert decision_of(done) == "deny"
    assert FAKE[kind] not in done.stdout, "the reason must not echo the credential"


def test_edits_and_multi_edits_are_scanned_too():
    edit = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "a.py", "new_string": FAKE["aws"]},
    }
    multi = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": "a.py",
            "edits": [{"new_string": "x"}, {"new_string": FAKE["groq"]}],
        },
    }
    assert decision_of(run_hook("guard_secrets.py", edit)) == "deny"
    assert decision_of(run_hook("guard_secrets.py", multi)) == "deny"


@pytest.mark.parametrize("name", [".env", ".env.local", "apps/api/.env.production"])
def test_env_files_are_not_written(name):
    assert decision_of(run_hook("guard_secrets.py", write(name, "REGION=ap-south-1\n"))) == "deny"


def test_env_example_and_ordinary_code_are_allowed():
    example = write(".env.example", "BEDROCK_ANSWER_MODEL_ID=\n")
    code = write(
        "apps/api/handler.py",
        "import os\nMODEL = os.environ['BEDROCK_ANSWER_MODEL_ID']\n",
    )
    assert decision_of(run_hook("guard_secrets.py", example)) is None
    assert decision_of(run_hook("guard_secrets.py", code)) is None


# --- session_start ---------------------------------------------------------------------------


def test_session_start_surfaces_the_next_step():
    done = run_hook("session_start.py", {"hook_event_name": "SessionStart", "source": "startup"})
    assert done.returncode == 0
    assert "Next session starts here" in done.stdout


# --- stop_gate -------------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git not available")
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "init"], cwd=tmp_path, check=True)
    return tmp_path


def test_stop_gate_passes_a_clean_tree(repo):
    assert run_hook("stop_gate.py", {"stop_hook_active": False}, repo).returncode == 0


@pytest.mark.skipif(
    shutil.which("ruff") is None and importlib.util.find_spec("ruff") is None,
    reason="ruff not installed",
)
def test_stop_gate_blocks_a_lint_failure_once(repo):
    (repo / "broken.py").write_text("import os\n", encoding="utf-8")

    first = run_hook("stop_gate.py", {"stop_hook_active": False}, repo)
    assert first.returncode == 2
    assert "ruff check failed" in first.stderr

    # Claude is already continuing because of this hook: never trap the session in a loop.
    second = run_hook("stop_gate.py", {"stop_hook_active": True}, repo)
    assert second.returncode == 0


# --- wiring ------------------------------------------------------------------------------------


def test_every_hook_in_settings_exists_and_is_tested_here():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    referenced = {
        Path(arg).name
        for groups in settings["hooks"].values()
        for group in groups
        for handler in group["hooks"]
        for arg in handler.get("args", [])
    }
    assert referenced == {p.name for p in HOOKS.glob("*.py")}
    source = Path(__file__).read_text(encoding="utf-8")
    for name in referenced - {"format_changed.py"}:
        assert name in source, f"{name} has no test"
