"""Ingestion Lambda. Invoked asynchronously by `complete` with `{"action": "ingest", ...}`, and once
after each deploy with `{"action": "ensure_index"}`, so the API role never needs index-write access.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from aws_lambda_powertools import Logger

from crownx.app.ingestion import IngestionWorker

logger = Logger(service="crownx-ingest")


def handle(event: dict[str, Any], worker: IngestionWorker) -> dict[str, Any]:
    action = event.get("action")
    if action == "ensure_index":
        created = worker.ensure_index()
        # `created` is a reserved LogRecord attribute, so the key is namespaced.
        logger.info("index ensured", extra={"index_created": created})
        return {"status": "ok", "created": created}
    if action == "ingest":
        workspace_id, document_id = str(event["workspace_id"]), str(event["document_id"])
        logger.append_keys(workspace_id=workspace_id, document_id=document_id)
        document = worker.ingest(workspace_id, document_id)
        status = document.status.value if document else "skipped"
        logger.info("ingestion finished", extra={"status": status})
        return {"status": status}
    raise ValueError(f"unknown action: {action!r}")


@lru_cache(maxsize=1)
def _live_worker() -> IngestionWorker:
    import boto3

    from crownx.adapters.bedrock import TitanEmbedder
    from crownx.adapters.dynamo import DynamoMetadataStore
    from crownx.adapters.opensearch import OpenSearchIndex, build_client
    from crownx.adapters.s3 import S3ObjectStore
    from crownx.config import get_settings

    settings = get_settings()
    session = boto3.Session(region_name=settings.aws_region)
    return IngestionWorker(
        store=DynamoMetadataStore(session.resource("dynamodb").Table(settings.table_name)),
        objects=S3ObjectStore(session.client("s3"), settings.documents_bucket),
        embedder=TitanEmbedder(
            session.client("bedrock-runtime"), settings.bedrock_embedding_model_id
        ),
        index=OpenSearchIndex(
            build_client(
                settings.opensearch_endpoint,
                settings.aws_region,
                session.get_credentials(),
                timeout=60,
            ),
            settings.opensearch_index,
        ),
    )


@logger.inject_lambda_context(clear_state=True)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return handle(event, _live_worker())
