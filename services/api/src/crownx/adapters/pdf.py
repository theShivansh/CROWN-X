"""PDF text extraction with pypdf, page by page. Parsing only: no network, no code from the file."""

from __future__ import annotations

import io
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

# Spaces, tabs and no-break spaces; newlines are kept.
_SPACES = re.compile(r"[ \t ]+")


class UnreadablePdf(Exception):
    """The bytes aren't a PDF pypdf can open (corrupt, truncated or encrypted)."""


def read_pdf_pages(raw: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise UnreadablePdf("encrypted")
        return [_clean(page.extract_text() or "") for page in reader.pages]
    except (PdfReadError, ValueError, KeyError, TypeError) as error:
        raise UnreadablePdf(str(error)) from error


def _clean(text: str) -> str:
    """PDF text layers often space words with two or more characters ("paper  forms"). Collapse
    runs of spaces within each line so quotes, search and citations see the words as written."""
    return "\n".join(_SPACES.sub(" ", line).strip() for line in text.splitlines())
