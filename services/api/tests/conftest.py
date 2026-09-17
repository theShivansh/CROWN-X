from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from fakes import FakeIndex, FakeIngest, FakeObjects, FakeStore

from crownx.app.api import build_resolver
from crownx.app.service import CrownService, Limits

MAX_BYTES = 1024
MAX_DOCS = 3


@dataclass
class ApiHarness:
    store: FakeStore
    objects: FakeObjects
    ingest: FakeIngest
    index: FakeIndex
    service: CrownService

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


@pytest.fixture
def api() -> ApiHarness:
    store, objects, ingest, index = FakeStore(), FakeObjects(), FakeIngest(), FakeIndex()
    service = CrownService(
        store=store,
        objects=objects,
        ingest=ingest,
        index=index,
        limits=Limits(
            max_upload_bytes=MAX_BYTES,
            max_documents_per_workspace=MAX_DOCS,
            upload_url_expiry_seconds=300,
        ),
    )
    return ApiHarness(store, objects, ingest, index, service)
