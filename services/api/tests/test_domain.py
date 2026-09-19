"""Pure domain rules: the import boundary, IDs and upload validation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from crownx.domain.errors import InvalidRequest, TooLarge, UnsupportedType
from crownx.domain.ids import is_document_id, is_workspace_id, new_document_id, new_workspace_id
from crownx.domain.uploads import object_key, sanitize_filename, validate_upload

DOMAIN = Path(__file__).resolve().parent.parent / "src" / "crownx" / "domain"
BANNED = (
    "boto3",
    "botocore",
    "opensearchpy",
    "aws_lambda_powertools",
    "crownx.adapters",
    "crownx.app",
)


def test_domain_imports_no_aws_sdk_or_adapters():
    offenders = []
    files = sorted(DOMAIN.rglob("*.py"))
    assert files, "domain package not found"
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            offenders += [
                f"{path.name}: {name}"
                for name in names
                if any(name == banned or name.startswith(f"{banned}.") for banned in BANNED)
            ]
    assert offenders == []


def test_ids_are_prefixed_unguessable_and_recognised():
    workspace_ids = {new_workspace_id() for _ in range(200)}
    assert len(workspace_ids) == 200
    assert all(is_workspace_id(w) and len(w) == 3 + 22 for w in workspace_ids)
    assert is_document_id(new_document_id())
    for bad in ("ws_short", "ws_" + "a" * 23, "doc_" + "a" * 22, "", "ws_" + "a" * 21 + "/"):
        assert not is_workspace_id(bad)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("brief v1.md", "brief-v1.md"),
        ("../../etc/passwd.md", "passwd.md"),
        ("C:\\Users\\team\\Notes.TXT", "Notes.txt"),
        ("..md", "document.md"),
        ("x" * 300 + ".md", "x" * 117 + ".md"),
    ],
)
def test_filenames_are_sanitized_and_keep_their_extension(raw, expected):
    assert sanitize_filename(raw) == expected


def test_supported_upload_is_accepted_with_its_content_type():
    spec = validate_upload("Meeting notes.md", 500, max_bytes=1024)
    assert (spec.filename, spec.content_type, spec.size_bytes) == (
        "Meeting-notes.md",
        "text/markdown",
        500,
    )
    assert object_key("ws_a", "doc_b", spec.filename) == "ws/ws_a/doc_b/Meeting-notes.md"


def test_unsupported_type_names_the_supported_types():
    with pytest.raises(UnsupportedType) as caught:
        validate_upload("budget.xlsx", 10, max_bytes=1024)
    assert ".xlsx" in caught.value.message and ".md, .txt" in caught.value.message
    assert caught.value.status == 400


def test_oversize_declaration_states_the_limit():
    with pytest.raises(TooLarge) as caught:
        validate_upload("big.txt", 2048, max_bytes=1024)
    assert caught.value.status == 413
    assert "1,024 bytes" in caught.value.message


@pytest.mark.parametrize(("name", "size"), [("empty.md", 0), ("negative.md", -5), ("  ", 10)])
def test_empty_or_nameless_uploads_are_invalid(name, size):
    with pytest.raises(InvalidRequest):
        validate_upload(name, size, max_bytes=1024)


def test_utc_now_strictly_increases_even_on_a_coarse_clock():
    """Upload order is a selection signal (ADR-020): two uploads never share a timestamp."""
    from crownx.domain.models import utc_now

    stamps = [utc_now() for _ in range(2000)]
    assert stamps == sorted(stamps) and len(set(stamps)) == len(stamps)
