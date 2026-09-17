"""Adapter behaviour that can be checked without network access."""

from __future__ import annotations

import base64
import json

import boto3

from crownx.adapters.s3 import S3ObjectStore


def test_presigned_post_policy_enforces_size_and_content_type():
    client = boto3.client(
        "s3",
        region_name="ap-south-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    post = S3ObjectStore(client, "crownx-docs-test").presigned_post(
        "ws/ws_a/doc_b/brief.md", "text/markdown", max_bytes=5_000_000, expires_in=300
    )

    assert post["url"].startswith("https://")
    assert post["fields"]["key"] == "ws/ws_a/doc_b/brief.md"
    assert post["fields"]["Content-Type"] == "text/markdown"
    policy = json.loads(base64.b64decode(post["fields"]["policy"]))
    conditions = policy["conditions"]
    assert ["content-length-range", 1, 5_000_000] in conditions
    assert {"Content-Type": "text/markdown"} in conditions
    assert {"bucket": "crownx-docs-test"} in conditions
    assert {"key": "ws/ws_a/doc_b/brief.md"} in conditions
