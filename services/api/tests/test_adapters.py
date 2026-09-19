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


class _ClaimTable(_Table):
    """Adds the low-level paginated query and the batch writer that claim replacement uses."""

    def __init__(self) -> None:
        super().__init__()
        table = self

        class Client:
            def get_paginator(self, name: str):
                assert name == "query"

                class Pages:
                    def paginate(self, **kwargs):
                        values = kwargs["ExpressionAttributeValues"]
                        pk, prefix = values[":pk"]["S"], values[":prefix"]["S"]
                        assert kwargs["ConsistentRead"] is True
                        items = [
                            {k: {"S": v} for k, v in item.items()}
                            for (p, s), item in sorted(table.items.items())
                            if p == pk and s.startswith(prefix)
                        ]
                        return [{"Items": items}]

                return Pages()

        self.meta = type("Meta", (), {"client": Client()})()

    def batch_writer(self):
        table = self

        class Batch:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def put_item(self, Item: dict) -> None:  # noqa: N803
                table.items[(Item["PK"], Item["SK"])] = Item

            def delete_item(self, Key: dict) -> None:  # noqa: N803
                table.items.pop((Key["PK"], Key["SK"]))

        return Batch()


def test_claims_are_replaced_per_document_and_listed_per_workspace():
    from crownx.adapters.dynamo import DynamoMetadataStore
    from crownx.domain.claims import Claim

    def claim(claim_id: str, document_id: str, value: str) -> Claim:
        return Claim(
            claim_id=claim_id, workspace_id="ws_A", document_id=document_id, filename="f.md",
            subject="budget", attribute="cap", value_type="number", raw_value=f"₹{value}",
            normalized_value=value, unit="INR", quote=f"Budget cap: ₹{value}", char_start=0,
            char_end=20, value_start=12, value_end=20, source_chunk_id=f"{document_id}:0",
            uploaded_at="2026-09-19T00:00:00Z", trigger="Budget cap",
            confidence={"extraction": 1.0},
        )  # fmt: skip

    table = _ClaimTable()
    store = DynamoMetadataStore(table)
    store.replace_claims("ws_A", "doc_1", [claim("cl_1", "doc_1", "50000")])
    store.replace_claims("ws_A", "doc_2", [claim("cl_2", "doc_2", "45000")])
    assert ("WS#ws_A", "CLAIM#budget#cap#cl_1") in table.items

    store.replace_claims("ws_A", "doc_1", [claim("cl_3", "doc_1", "45000")])  # re-ingested

    got = {c.claim_id: c for c in store.list_claims("ws_A")}
    assert set(got) == {"cl_2", "cl_3"}  # doc_1's old claim is gone; doc_2's is untouched
    assert got["cl_3"].confidence == {"extraction": 1.0}
    assert store.list_claims("ws_B") == []
