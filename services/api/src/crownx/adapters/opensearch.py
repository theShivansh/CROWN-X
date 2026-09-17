"""OpenSearch Service client, signed with the function's IAM role (ADR-011). Retrieval arrives in S3."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from opensearchpy import OpenSearch, Urllib3AWSV4SignerAuth, Urllib3HttpConnection


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
