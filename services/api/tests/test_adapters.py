"""Adapter behaviour that can be checked without network access."""

from __future__ import annotations

import base64
import hashlib
import io
import json

import boto3
from botocore.response import StreamingBody

from crownx.adapters.s3 import S3_CLIENT_CONFIG, S3ObjectStore


def test_presigned_post_policy_enforces_size_and_content_type_on_the_regional_endpoint():
    client = boto3.client(
        "s3",
        region_name="ap-south-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        config=S3_CLIENT_CONFIG,
    )
    post = S3ObjectStore(client, "crownx-docs-test").presigned_post(
        "ws/ws_a/doc_b/brief.md", "text/markdown", max_bytes=5_000_000, expires_in=300
    )

    # Not the global s3.amazonaws.com host, which redirects for new buckets and breaks CORS POSTs.
    assert post["url"] == "https://crownx-docs-test.s3.ap-south-1.amazonaws.com/"
    assert post["fields"]["x-amz-algorithm"] == "AWS4-HMAC-SHA256"
    assert post["fields"]["key"] == "ws/ws_a/doc_b/brief.md"
    assert post["fields"]["Content-Type"] == "text/markdown"
    policy = json.loads(base64.b64decode(post["fields"]["policy"]))
    conditions = policy["conditions"]
    assert ["content-length-range", 1, 5_000_000] in conditions
    assert {"Content-Type": "text/markdown"} in conditions
    assert {"bucket": "crownx-docs-test"} in conditions
    assert {"key": "ws/ws_a/doc_b/brief.md"} in conditions


class _GetObjectClient:
    """Returns a real botocore StreamingBody, the way `get_object` does on a live client."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self.closed = False

    def get_object(self, Bucket: str, Key: str) -> dict:  # noqa: N803  # boto3's parameter names
        stream = io.BytesIO(self._data)
        store = self

        class _Raw(io.BytesIO):
            def close(self) -> None:
                store.closed = True
                super().close()

        raw = _Raw(stream.getvalue())
        return {"Body": StreamingBody(raw, len(self._data))}


def test_sha256_streams_the_object_and_closes_it():
    client = _GetObjectClient(b"deadline moves to 22 September\n" * 100)
    store = S3ObjectStore(client, "crownx-docs-test")
    assert store.sha256("ws/x/doc/brief.md") == hashlib.sha256(client._data).hexdigest()
    assert client.closed


def test_read_bytes_returns_the_whole_object():
    client = _GetObjectClient(b"# Brief\n\nSubmissions close on 20 September.\n")
    store = S3ObjectStore(client, "crownx-docs-test")
    assert store.read_bytes("ws/x/doc/brief.md") == client._data
    assert client.closed


class _Table:
    """Just enough of a boto3 Table for put/get by key; the condition is checked by hand."""

    name = "crownx-test"

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict] = {}
        self.meta = type("Meta", (), {"client": object()})()

    def put_item(self, Item: dict, ConditionExpression=None) -> None:  # noqa: N803
        key = (Item["PK"], Item["SK"])
        if ConditionExpression is not None and key in self.items:
            raise AssertionError("conditional put on an existing key")
        self.items[key] = Item

    def get_item(self, Key: dict, ConsistentRead: bool = False) -> dict:  # noqa: N803
        item = self.items.get((Key["PK"], Key["SK"]))
        return {"Item": item} if item else {}


def test_query_records_round_trip_through_dynamodb_with_exact_scores():
    from crownx.adapters.dynamo import DynamoMetadataStore
    from crownx.domain.models import QueryRecord

    table = _Table()
    store = DynamoMetadataStore(table)
    record = QueryRecord(
        query_id="qry_AAAAAAAAAAAAAAAAAAAAAA",
        workspace_id="ws_BBBBBBBBBBBBBBBBBBBBBB",
        question="When do submissions close?",
        status="retrieved",
        evidence=[{"evidence_id": "ev_1", "quoted_span": "₹50,000", "retrieval_score": 0.032787}],
        created_at="2026-09-18T10:00:00.000000Z",
        request_id="req_x",
        retrieval_ms=42,
    )
    store.put_query(record)

    [(pk, sk)] = table.items
    assert (pk, sk) == ("WS#ws_BBBBBBBBBBBBBBBBBBBBBB", f"QUERY#{record.query_id}")
    assert store.get_query(record.workspace_id, record.query_id) == record
    assert store.get_query("ws_CCCCCCCCCCCCCCCCCCCCCC", record.query_id) is None
