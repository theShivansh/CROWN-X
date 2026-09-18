"""Split a document into retrievable chunks whose offsets point back into the document text.

Rule (M1): split at Markdown headings, then at blank-line paragraphs; pack paragraphs into chunks of
about `target_chars`, and start each following chunk up to `overlap_chars` earlier, at a word
boundary, so a sentence cut between chunks still appears whole in one of them. A paragraph longer
than the target is cut at whitespace. `text[chunk.char_start:chunk.char_end] == chunk.text` always
holds, because the UI highlights the exact passage from these offsets.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

_HEADING = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t#]*$", re.MULTILINE)
_BLANK_LINES = re.compile(r"\n[ \t]*(?:\n[ \t]*)+")


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    text: str
    char_start: int
    char_end: int
    section: str | None


def normalize_text(raw: str) -> str:
    """One newline convention, and no byte-order mark, so offsets are stable across platforms."""
    return raw.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def chunk_text(text: str, target_chars: int = 1000, overlap_chars: int = 120) -> list[Chunk]:
    if target_chars <= overlap_chars:
        raise ValueError("target_chars must be larger than overlap_chars")
    chunks: list[Chunk] = []
    for section_start, section_end, heading in _sections(text):
        window_start: int | None = None
        window_end = 0
        for piece_start, piece_end in _pieces(text, section_start, section_end, target_chars):
            if window_start is None:
                window_start, window_end = piece_start, piece_end
            elif piece_end - window_start <= target_chars:
                window_end = piece_end
            else:
                chunks.append(_chunk(text, len(chunks), window_start, window_end, heading))
                window_start = _overlap_start(
                    text, window_start, window_end, piece_start, overlap_chars
                )
                window_end = piece_end
        if window_start is not None:
            chunks.append(_chunk(text, len(chunks), window_start, window_end, heading))
    return chunks


def _chunk(text: str, ordinal: int, start: int, end: int, heading: str | None) -> Chunk:
    return Chunk(
        ordinal=ordinal, text=text[start:end], char_start=start, char_end=end, section=heading
    )


def _sections(text: str) -> list[tuple[int, int, str | None]]:
    marks = list(_HEADING.finditer(text))
    if not marks:
        return [(0, len(text), None)]
    sections: list[tuple[int, int, str | None]] = []
    if marks[0].start() > 0:
        sections.append((0, marks[0].start(), None))
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        sections.append((mark.start(), end, mark.group(1).strip()))
    return sections


def _pieces(text: str, start: int, end: int, target: int) -> Iterator[tuple[int, int]]:
    """Paragraph spans inside [start, end), with long paragraphs cut at whitespace."""
    position = start
    for blank in _BLANK_LINES.finditer(text, start, end):
        yield from _split_long(text, position, blank.start(), target)
        position = blank.end()
    yield from _split_long(text, position, end, target)


def _split_long(text: str, start: int, end: int, target: int) -> Iterator[tuple[int, int]]:
    start, end = _trim(text, start, end)
    while end - start > target:
        cut = start + target
        for index in range(start + target, start + target // 2, -1):
            if text[index - 1].isspace():
                cut = index
                break
        piece = _trim(text, start, cut)
        if piece[0] < piece[1]:
            yield piece
        start, end = _trim(text, cut, end)
    if start < end:
        yield start, end


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _overlap_start(
    text: str, window_start: int, window_end: int, next_start: int, overlap: int
) -> int:
    """The first word start at or after `window_end - overlap`, never before the window's own start."""
    candidate = max(window_end - overlap, window_start + 1)
    for index in range(candidate, next_start):
        if not text[index].isspace() and text[index - 1].isspace():
            return index
    return next_start


PAGE_SEPARATOR = "\n\n"


def chunk_pages(
    pages: list[str], target_chars: int = 1000, overlap_chars: int = 120
) -> tuple[str, list[Chunk]]:
    """Chunk a paged document (a PDF) page by page, so no chunk spans two pages.

    Returns the document text (pages joined by a blank line) and chunks whose offsets point into it,
    with `section` set to "Page N" (1-based) for citations.
    """
    texts = [normalize_text(page) for page in pages]
    chunks: list[Chunk] = []
    offset = 0
    for number, page in enumerate(texts, start=1):
        for chunk in chunk_text(page, target_chars, overlap_chars):
            chunks.append(
                Chunk(
                    ordinal=len(chunks),
                    text=chunk.text,
                    char_start=offset + chunk.char_start,
                    char_end=offset + chunk.char_end,
                    section=f"Page {number}",
                )
            )
        offset += len(page) + len(PAGE_SEPARATOR)
    return PAGE_SEPARATOR.join(texts), chunks
