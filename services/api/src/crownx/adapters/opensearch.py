"""OpenSearch Service client, signed with the function's IAM role (ADR-011)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from opensearchpy import (
    NotFoundError,
    OpenSearch,
    RequestError,
    Urllib3AWSV4SignerAuth,
    Urllib3HttpConnection,
    helpers,
)

from crownx.adapters.ports import SearchHit


def build_client(endpoint: str, region: str, credentials: Any, timeout: int = 10) -> OpenSearch:
    host = urlparse(endpoint).hostname if "://" in endpoint else endpoint
    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=Urllib3AWSV4SignerAuth(credentials, region, "es"),
        use_ssl=True,
        verify_certs=True,
        connection_class=Urllib3HttpConnection,
        timeout=timeout,
    )


class OpenSearchIndex:
    def __init__(self, client: OpenSearch, index: str) -> None:
        self._client = client
        self._index = index

    def index_exists(self) -> bool:
        return bool(self._client.indices.exists(index=self._index))

    def ensure_index(self, body: dict) -> bool:
        if self.index_exists():
            return False
        try:
            self._client.indices.create(index=self._index, body=body)
        except RequestError as error:
            if error.error == "resource_already_exists_exception":
                return False  # created concurrently: the goal is met
            raise
        return True

    def index_chunks(self, chunks: list[dict]) -> None:
        actions = (
            {"_op_type": "index", "_index": self._index, "_id": chunk["chunk_id"], "_source": chunk}
            for chunk in chunks
        )
        # raise_on_error stays on: a partially indexed document must not be marked ready.
        helpers.bulk(self._client, actions, refresh="wait_for", chunk_size=200)

    def search(self, body: dict) -> list[SearchHit]:
        try:
            response = self._client.search(index=self._index, body=body)
        except NotFoundError:
            return []  # no document has been ingested yet, so there is nothing to find
        return [
            SearchHit(chunk_id=hit["_id"], score=float(hit["_score"] or 0.0), source=hit["_source"])
            for hit in response["hits"]["hits"]
        ]
