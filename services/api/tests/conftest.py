from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from fakes import FakeAnswerer, FakeEmbedder, FakeIndex, FakeIngest, FakeObjects, FakeStore

from crownx.app.api import build_resolver
from crownx.app.ingestion import IngestionWorker
from crownx.app.service import CrownService, Limits

MAX_BYTES = 64 * 1024
MAX_DOCS = 3
TOP_K = 4


@dataclass
class ApiHarness:
    store: FakeStore
    objects: FakeObjects
    ingest: FakeIngest
    index: FakeIndex
    embedder: FakeEmbedder
    service: CrownService
    worker: IngestionWorker
    answerer: FakeAnswerer

    def call(
        self,
        method: str,
        path: str,
        body: Any = None,
        raw_body: str | None = None,
        factory: Callable[[], CrownService] | None = None,
    ) -> tuple[int, dict, dict]:
        resolver = build_resolver(factory or (lambda: self.service))
        event = {
            "version": "2.0",
            "routeKey": "$default",
            "rawPath": path,
            "rawQueryString": "",
            "headers": {"content-type": "application/json"},
            "requestContext": {
                "accountId": "000000000000",
                "apiId": "test",
                "domainName": "api.example.test",
                "domainPrefix": "api",
                "http": {
                    "method": method,
                    "path": path,
                    "protocol": "HTTP/1.1",
                    "sourceIp": "127.0.0.1",
                    "userAgent": "pytest",
                },
                "requestId": "Tst123abc=",
                "routeKey": "$default",
                "stage": "$default",
                "time": "17/Sep/2026:12:00:00 +0000",
                "timeEpoch": 1789646400000,
            },
            "body": raw_body
            if raw_body is not None
            else (None if body is None else json.dumps(body)),
            "isBase64Encoded": False,
        }
        response = resolver.resolve(event, object())
        return response["statusCode"], json.loads(response["body"]), response.get("headers") or {}

    def new_workspace(self) -> str:
        status, body, _ = self.call("POST", "/workspaces")
        assert status == 201
        return body["workspace"]["workspace_id"]

    def upload(self, workspace_id: str, filename: str, content: bytes, ingest: bool = True) -> str:
        """Upload through the API as the browser would, then run the ingestion worker."""
        status, body, _ = self.call(
            "POST",
            f"/workspaces/{workspace_id}/documents/upload-url",
            {"filename": filename, "size_bytes": len(content)},
        )
        assert status == 201, body
        document_id = body["document"]["document_id"]
        self.objects.objects[self.objects.posts[-1]["key"]] = content
        status, body, _ = self.call(
            "POST", f"/workspaces/{workspace_id}/documents/{document_id}/complete"
        )
        assert status == 200, body
        if ingest:
            self.worker.ingest(workspace_id, document_id)
        return document_id


@pytest.fixture
def api() -> ApiHarness:
    store, objects, ingest = FakeStore(), FakeObjects(), FakeIngest()
    index, embedder, answerer = FakeIndex(), FakeEmbedder(), FakeAnswerer()
    service = CrownService(
        store=store,
        objects=objects,
        ingest=ingest,
        index=index,
        embedder=embedder,
        limits=Limits(
            max_upload_bytes=MAX_BYTES,
            max_documents_per_workspace=MAX_DOCS,
            upload_url_expiry_seconds=300,
            retrieval_top_k=TOP_K,
        ),
        answerer=answerer,
    )
    worker = IngestionWorker(store=store, objects=objects, embedder=embedder, index=index)
    return ApiHarness(store, objects, ingest, index, embedder, service, worker, answerer)
