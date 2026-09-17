"""Chunk boundaries, sections and offsets: the UI highlights passages from these offsets."""

from __future__ import annotations

from pathlib import Path

import pytest

from crownx.domain.chunking import chunk_text, normalize_text

SCENARIO = Path(__file__).resolve().parents[3] / "demo" / "SCENARIO.md"


def assert_round_trip(text: str, chunks) -> None:
    for chunk in chunks:
        assert text[chunk.char_start : chunk.char_end] == chunk.text
        assert chunk.text == chunk.text.strip() and chunk.text


def test_empty_or_blank_text_has_no_chunks():
    assert chunk_text("") == []
    assert chunk_text(" \n\n \t\n") == []


def test_short_document_is_one_chunk_with_its_heading():
    text = "# Timeline\n\nFinal submissions close on 20 September 2026.\n"
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].section == "Timeline"
    assert "20 September 2026" in chunks[0].text
    assert_round_trip(text, chunks)


def test_sections_follow_the_nearest_heading_and_preamble_has_none():
    text = "Team Lantern notes\n\n# Decisions\n\nDeadline confirmed.\n\n## Budget\n\nFollow sheet v2.\n"
    chunks = chunk_text(text, target_chars=200, overlap_chars=20)
    assert [(c.section, c.text.splitlines()[-1]) for c in chunks] == [
        (None, "Team Lantern notes"),
        ("Decisions", "Deadline confirmed."),
        ("Budget", "Follow sheet v2."),
    ]
    assert_round_trip(text, chunks)


def test_paragraphs_pack_to_the_target_with_word_boundary_overlap():
    paragraphs = [f"Paragraph {n} " + "word " * 40 for n in range(12)]
    text = "\n\n".join(p.strip() for p in paragraphs)
    chunks = chunk_text(text, target_chars=600, overlap_chars=120)
    assert len(chunks) > 2
    assert_round_trip(text, chunks)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert current.char_start < previous.char_end, "consecutive chunks overlap"
        assert previous.char_end - current.char_start <= 120 + 5
        assert current.char_start == 0 or text[current.char_start - 1].isspace()
        assert len(current.text) <= 600 + 120
    covered = set()
    for chunk in chunks:
        covered.update(range(chunk.char_start, chunk.char_end))
    assert all(i in covered for i, ch in enumerate(text) if not ch.isspace())


def test_a_long_paragraph_is_cut_at_whitespace():
    text = " ".join(f"token{n}" for n in range(600))
    chunks = chunk_text(text, target_chars=1000, overlap_chars=120)
    assert len(chunks) > 1
    assert_round_trip(text, chunks)
    for chunk in chunks:
        assert not chunk.text.startswith(" ") and chunk.text.split()[0].startswith("token")
        assert len(chunk.text) <= 1000 + 120


def test_chunking_is_deterministic():
    text = SCENARIO.read_text(encoding="utf-8")
    assert chunk_text(text) == chunk_text(text)


def test_the_demo_scenario_round_trips_and_keeps_its_deadline_lines():
    text = normalize_text(SCENARIO.read_bytes().decode("utf-8"))
    chunks = chunk_text(text)
    assert_round_trip(text, chunks)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    assert any("Final submissions close on 20 September 2026." in c.text for c in chunks)


@pytest.mark.parametrize("raw", ["\ufeffa\r\nb\rc", "a\nb\nc"])
def test_normalize_text_uses_one_newline_convention(raw):
    assert normalize_text(raw) == "a\nb\nc"


def test_overlap_must_be_smaller_than_target():
    with pytest.raises(ValueError):
        chunk_text("text", target_chars=100, overlap_chars=100)
