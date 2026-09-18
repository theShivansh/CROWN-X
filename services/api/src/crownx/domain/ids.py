"""Unguessable IDs. For the event, the workspace ID is the access boundary (SECURITY §3)."""

from __future__ import annotations

import re
import secrets

_TOKEN = r"[A-Za-z0-9_-]{22}"
_WORKSPACE_ID = re.compile(rf"ws_{_TOKEN}")
_DOCUMENT_ID = re.compile(rf"doc_{_TOKEN}")
_QUERY_ID = re.compile(rf"qry_{_TOKEN}")


def _token() -> str:
    # 16 random bytes encode to exactly 22 URL-safe characters (about 128 bits).
    return secrets.token_urlsafe(16)


def new_workspace_id() -> str:
    return f"ws_{_token()}"


def new_document_id() -> str:
    return f"doc_{_token()}"


def is_workspace_id(value: str) -> bool:
    return _WORKSPACE_ID.fullmatch(value) is not None


def is_document_id(value: str) -> bool:
    return _DOCUMENT_ID.fullmatch(value) is not None


def new_query_id() -> str:
    return f"qry_{_token()}"


def is_query_id(value: str) -> bool:
    return _QUERY_ID.fullmatch(value) is not None
