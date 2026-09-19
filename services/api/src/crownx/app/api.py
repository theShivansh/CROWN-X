"""HTTP API Lambda. Every response carries `request_id`; every error uses one envelope (SRS §6)."""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response, content_types
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from crownx.app.service import CrownService
from crownx.domain.conflicts import audit_record
from crownx.domain.errors import DomainError, InvalidRequest

logger = Logger(service="crownx-api")


class UploadUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)


def request_id_of(event: dict[str, Any]) -> str:
    return f"req_{(event.get('requestContext') or {}).get('requestId') or 'local'}"


def build_resolver(service: Callable[[], CrownService]) -> APIGatewayHttpResolver:
    app = APIGatewayHttpResolver()

    def rid() -> str:
        return request_id_of(app.current_event.raw_event)

    def reply(body: dict[str, Any], status: int = 200) -> Response:
        request_id = rid()
        return Response(
            status_code=status,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({**body, "request_id": request_id}),
            headers={"x-request-id": request_id},
        )

    def error(status: int, code: str, message: str) -> Response:
        request_id = rid()
        return Response(
            status_code=status,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps(
                {"error": {"code": code, "message": message, "request_id": request_id}}
            ),
            headers={"x-request-id": request_id},
        )

    def body_as(model: type[BaseModel]) -> Any:
        try:
            return model.model_validate(json.loads(app.current_event.body or ""))
        except ValueError as exc:  # invalid JSON, or a pydantic ValidationError
            if isinstance(exc, ValidationError):
                fields = sorted(
                    {".".join(str(p) for p in e["loc"]) or "body" for e in exc.errors()}
                )
                raise InvalidRequest(f"Check these fields: {', '.join(fields)}.") from exc
            raise InvalidRequest("The request body must be JSON.") from exc

    @app.exception_handler(DomainError)
    def domain_error(exc: DomainError) -> Response:
        logger.info("request rejected", extra={"error_code": exc.code, "status": exc.status})
        return error(exc.status, exc.code, exc.message)

    @app.exception_handler(Exception)
    def unexpected(exc: Exception) -> Response:
        logger.exception("unhandled error")
        return error(
            500,
            "internal_error",
            "Something went wrong on our side. Retry, and quote the request ID if it keeps failing.",
        )

    @app.not_found
    def not_found(_exc: Exception) -> Response:
        return error(404, "not_found", "No such endpoint.")

    @app.get("/health")
    def health() -> Response:
        try:
            live = service()
        except Exception:  # noqa: BLE001  # missing or invalid settings: report, don't crash
            logger.exception("configuration failed to load")
            return reply({"status": "degraded", "dependencies": {"config": "invalid"}}, 503)
        checks = live.health()
        healthy = all(value == "ok" for value in checks.values())
        return reply(
            {
                "status": "ok" if healthy else "degraded",
                "dependencies": checks,
                "providers": live.providers(),
            },
            200 if healthy else 503,
        )

    @app.post("/workspaces")
    def create_workspace() -> Response:
        workspace = service().create_workspace()
        return reply({"workspace": workspace.model_dump(mode="json")}, 201)

    @app.post("/workspaces/<workspace_id>/documents/upload-url")
    def upload_url(workspace_id: str) -> Response:
        request = body_as(UploadUrlRequest)
        ticket = service().create_upload(workspace_id, request.filename, request.size_bytes)
        return reply(
            {
                "document": ticket.document.public(),
                "upload": ticket.upload,
                "expires_in": ticket.expires_in,
            },
            201,
        )

    @app.post("/workspaces/<workspace_id>/documents/<document_id>/complete")
    def complete(workspace_id: str, document_id: str) -> Response:
        result = service().complete_upload(workspace_id, document_id)
        return reply({"document": result.document.public(), "duplicate": result.duplicate})

    @app.get("/workspaces/<workspace_id>/documents")
    def list_documents(workspace_id: str) -> Response:
        documents = service().list_documents(workspace_id)
        return reply({"documents": [d.public() for d in documents]})

    @app.post("/workspaces/<workspace_id>/query")
    def query(workspace_id: str) -> Response:
        request = body_as(QueryRequest)
        result = service().query(workspace_id, request.question, request_id=rid())
        return reply(
            {
                "query_id": result.query_id,
                "status": result.status,
                "evidence": result.evidence,
                "conflicts": result.conflicts or [],
            }
        )

    @app.get("/workspaces/<workspace_id>/conflicts")
    def list_conflicts(workspace_id: str) -> Response:
        groups = service().conflicts(workspace_id)
        logger.info(
            "conflicts listed",
            extra={"conflicts": [item for group in groups for item in audit_record(group)]},
        )
        return reply({"conflicts": groups})

    @app.get("/workspaces/<workspace_id>/timeline")
    def value_timeline(workspace_id: str) -> Response:
        params = app.current_event.query_string_parameters or {}
        view = service().timeline(
            workspace_id, params.get("subject", ""), params.get("attribute", "")
        )
        logger.info(
            "timeline listed",
            extra={
                "key": view["key"],
                "events": len(view["events"]),
                "selection_rule": view["selection_rule"],
            },
        )
        return reply(view)

    @app.post("/workspaces/<workspace_id>/queries/<query_id>/answer")
    def answer(workspace_id: str, query_id: str) -> Response:
        try:
            outcome = service().answer(workspace_id, query_id, request_id=rid())
        except DomainError as error:
            # Each model call and its outcome (for example http_429 then http_500), so a failed
            # answer can be diagnosed from the logs as well as the audit record.
            logger.warning(
                "answer not written",
                extra={"error_code": error.code, "attempts": list(getattr(error, "attempts", ()))},
            )
            raise
        logger.info(
            "answer written",
            extra={
                "answer_status": outcome.final.status,
                "answered_by_model": outcome.model_id,
                "attempts": list(outcome.attempts),
                "conflicts": list(outcome.conflicts),
            },
        )
        return reply(
            {
                "query_id": outcome.query_id,
                "status": outcome.final.status,
                "answer": outcome.final.answer,
                "claims": outcome.final.claims,
                "answer_provider": outcome.provider,
                "model_id": outcome.model_id,
                # The model that wrote this answer; after a fallback it isn't the configured one.
                "answered_by_model": outcome.model_id,
                "attempts": list(outcome.attempts),
            }
        )

    @app.get("/workspaces/<workspace_id>/workflow-suggestions")
    def workflow_suggestions(workspace_id: str) -> Response:
        """Read-only (ADR-018): repeated sequences of this workspace's own actions. Nothing runs."""
        suggestions, definitions = service().workflow_suggestions(workspace_id)
        return reply(
            {
                "suggestions": [s.model_dump(mode="json") for s in suggestions],
                "definitions": definitions,
                "automation": "none",
            }
        )

    return app


@lru_cache(maxsize=1)
def _live_service() -> CrownService:
    """Built once per cold start from the environment, so tests never touch AWS."""
    import boto3

    from crownx.adapters.dynamo import DynamoMetadataStore
    from crownx.adapters.ingest_queue import LambdaIngestQueue
    from crownx.adapters.opensearch import OpenSearchIndex, build_client
    from crownx.adapters.providers import ProviderRouter
    from crownx.adapters.s3 import S3_CLIENT_CONFIG, S3ObjectStore
    from crownx.app.service import Limits
    from crownx.config import get_settings

    settings = get_settings()
    session = boto3.Session(region_name=settings.aws_region)
    providers = ProviderRouter.build(settings, session)
    # Every log line from this container names the environment and providers (observability).
    logger.append_keys(**providers.describe())
    return CrownService(
        store=DynamoMetadataStore(session.resource("dynamodb").Table(settings.table_name)),
        objects=S3ObjectStore(
            session.client("s3", config=S3_CLIENT_CONFIG), settings.documents_bucket
        ),
        ingest=LambdaIngestQueue(session.client("lambda"), settings.ingest_function_name),
        index=OpenSearchIndex(
            build_client(
                settings.opensearch_endpoint, settings.aws_region, session.get_credentials()
            ),
            settings.opensearch_index,
        ),
        embedder=providers.embedder,
        namespace=providers.namespace,
        answerer=providers.answerer,
        reranker=providers.reranker,
        providers=providers.describe(),
        limits=Limits(
            max_upload_bytes=settings.max_upload_bytes,
            max_documents_per_workspace=settings.max_documents_per_workspace,
            upload_url_expiry_seconds=settings.upload_url_expiry_seconds,
            retrieval_top_k=settings.retrieval_top_k,
            retrieval_score_floor=settings.retrieval_score_floor,
        ),
    )


_resolver = build_resolver(_live_service)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.set_correlation_id(request_id_of(event))
    return _resolver.resolve(event, context)
