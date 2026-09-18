"""PDF text extraction with pypdf, page by page. Parsing only: no network, no code from the file."""

from __future__ import annotations

import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class UnreadablePdf(Exception):
    """The bytes aren't a PDF pypdf can open (corrupt, truncated or encrypted)."""


def read_pdf_pages(raw: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise UnreadablePdf("encrypted")
        return [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, ValueError, KeyError, TypeError) as error:
        raise UnreadablePdf(str(error)) from error
