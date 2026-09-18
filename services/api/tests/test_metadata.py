"""Version labels and source dates: exact on every demo document, and never guessed."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from crownx.domain.metadata import extract_metadata

DEMO = Path(__file__).resolve().parents[3] / "demo" / "documents"


def text_of(path: Path) -> str:
    if path.suffix == ".pdf":
        return "\n".join(page.extract_text() for page in PdfReader(path).pages)
    return path.read_text(encoding="utf-8")


# docs/SCENARIO.md §2 and §7: the version label and source date each document must yield.
EXPECTED = {
    "workspace-a/project-brief-v1.pdf": ("v1", "2026-08-31"),
    "workspace-a/api-limits-spec-v1.md": ("v1.0", "2026-09-03"),
    "workspace-a/organiser-update-3.txt": ("update 3", "2026-09-10"),
    "workspace-a/meeting-notes-sync-5.md": ("Sync 5", "2026-09-11"),
    "workspace-a/budget-sheet-v2.md": ("v2", "2026-09-12"),
    "workspace-a/team-roles.md": (None, None),
    "workspace-b/messmate-brief-v2.md": ("v2", "2026-09-09"),
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_each_demo_document_yields_its_scenario_metadata(name: str):
    metadata = extract_metadata(text_of(DEMO / name))
    assert (metadata.version_label, metadata.source_timestamp) == EXPECTED[name]


def test_a_date_in_the_body_is_never_the_documents_date():
    text = "Team notes\n\n- Deadline confirmed as 2026-09-22.\n"
    assert extract_metadata(text).source_timestamp is None


@pytest.mark.parametrize(
    "header",
    [
        "Date: 10/09/2026",  # day-month order unknown
        "Updated September 2026",  # no day
        "Updated 10 September",  # no year
        "Date: 31 September 2026",  # impossible
        "From 3 Sept 2026 to 10 Sept 2026",  # two different dates
    ],
)
def test_ambiguous_or_impossible_dates_stay_null(header: str):
    assert extract_metadata(f"{header}\n\nBody.").source_timestamp is None


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Updated 14 Sept 2026", "2026-09-14"),
        ("Date: 2026-09-14", "2026-09-14"),
        ("Revised September 14, 2026", "2026-09-14"),
        ("Posted 14 Sep. 2026 and again on 14 September 2026", "2026-09-14"),
    ],
)
def test_unambiguous_dates_are_read(header: str, expected: str):
    assert extract_metadata(f"{header}\n\nBody.").source_timestamp == expected


@pytest.mark.parametrize(
    ("header", "expected"),
    [("Spec · draft", "draft"), ("Plan, FINAL", "final"), ("Plan", None)],
)
def test_draft_and_final_labels(header: str, expected: str | None):
    assert extract_metadata(header).version_label == expected
