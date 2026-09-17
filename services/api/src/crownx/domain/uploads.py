"""Upload validation, done server-side before any byte is parsed (SRS FR-02, SECURITY T3)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath

from crownx.domain.errors import InvalidRequest, TooLarge, UnsupportedType

# `.pdf` joins in M2, with the empty-extraction error.
SUPPORTED_TYPES: dict[str, str] = {".md": "text/markdown", ".txt": "text/plain"}
_MAX_FILENAME_CHARS = 120
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class UploadSpec:
    filename: str
    content_type: str
    size_bytes: int


def sanitize_filename(name: str) -> str:
    """Keep only the base name, in a character set that is safe in an S3 key and a header."""
    base = unicodedata.normalize("NFKC", name).replace("\\", "/").rsplit("/", 1)[-1]
    # Split the extension off first, so the one validation checked is the one that's stored.
    suffix = PurePosixPath(base).suffix
    raw_stem = base[: len(base) - len(suffix)] if suffix else base
    suffix = _UNSAFE.sub("-", suffix).lower()
    stem = _UNSAFE.sub("-", raw_stem).strip(".-")[: _MAX_FILENAME_CHARS - len(suffix)]
    return f"{stem.strip('.-') or 'document'}{suffix}"


def validate_upload(filename: str, size_bytes: int, max_bytes: int) -> UploadSpec:
    if not filename.strip():
        raise InvalidRequest("A filename is required. Choose a .md or .txt file and try again.")
    supported = ", ".join(SUPPORTED_TYPES)
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if suffix not in SUPPORTED_TYPES:
        shown = suffix or "no extension"
        raise UnsupportedType(
            f"Files of type {shown} aren't supported. Supported types: {supported}."
        )
    if size_bytes <= 0:
        raise InvalidRequest("The file is empty. Upload a file with some text in it.")
    if size_bytes > max_bytes:
        raise TooLarge(
            f"The file is {size_bytes:,} bytes; the limit is {max_bytes:,} bytes "
            f"({max_bytes / (1024 * 1024):g} MB). Split it or upload a smaller file."
        )
    return UploadSpec(
        filename=sanitize_filename(filename),
        content_type=SUPPORTED_TYPES[suffix],
        size_bytes=size_bytes,
    )


def object_key(workspace_id: str, document_id: str, filename: str) -> str:
    return f"ws/{workspace_id}/{document_id}/{filename}"
