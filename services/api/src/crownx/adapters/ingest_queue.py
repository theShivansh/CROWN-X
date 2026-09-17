"""Hands a confirmed document to the ingestion Lambda without waiting for it."""

from __future__ import annotations

import json
from typing import Any


class LambdaIngestQueue:
    def __init__(self, client: Any, function_name: str) -> None:
        self._client = client
        self._function_name = function_name

    def enqueue(self, workspace_id: str, document_id: str) -> None:
        self._client.invoke(
            FunctionName=self._function_name,
            InvocationType="Event",
            Payload=json.dumps(
                {"action": "ingest", "workspace_id": workspace_id, "document_id": document_id}
            ).encode(),
        )
