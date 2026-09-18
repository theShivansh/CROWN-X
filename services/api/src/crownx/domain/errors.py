"""Errors the API turns into the one envelope `{"error": {"code", "message", "request_id"}}` (SRS §6).

Each message says what failed and what to do next, because the UI shows it as written.
"""

from __future__ import annotations


class DomainError(Exception):
    status: int = 400
    code: str = "invalid_request"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidRequest(DomainError):
    status = 400
    code = "invalid_request"


class UnsupportedType(DomainError):
    status = 400
    code = "unsupported_type"


class NotFound(DomainError):
    """Also used for IDs from another workspace, so existence never leaks (SECURITY T2)."""

    status = 404
    code = "not_found"


class UploadIncomplete(DomainError):
    status = 409
    code = "upload_incomplete"


class TooLarge(DomainError):
    status = 413
    code = "too_large"


class LimitReached(DomainError):
    status = 429
    code = "limit_reached"


class RetrievalUnavailable(DomainError):
    status = 503
    code = "retrieval_unavailable"


class AnswerUnavailable(DomainError):
    """The answer model can't be called (not configured, refused, or failing). No answer is made up."""

    status = 503
    code = "answer_unavailable"


class ModelTimeout(DomainError):
    status = 504
    code = "model_timeout"
