"""S3 document store. File bytes never pass through the API Lambda on upload (ARCHITECTURE §2)."""

from __future__ import annotations

import hashlib
from typing import Any

from botocore.exceptions import ClientError

from crownx.adapters.ports import ObjectInfo

_MISSING = {"404", "NoSuchKey", "NotFound"}


class S3ObjectStore:
    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def presigned_post(self, key: str, content_type: str, max_bytes: int, expires_in: int) -> dict:
        # S3 itself enforces the size limit and the content type; the API can't be bypassed.
        post = self._client.generate_presigned_post(
            Bucket=self._bucket,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=expires_in,
        )
        return {"url": post["url"], "fields": post["fields"]}

    def head(self, key: str) -> ObjectInfo | None:
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in _MISSING:
                return None  # not uploaded yet: the caller reports an incomplete upload
            raise
        return ObjectInfo(
            size_bytes=int(response["ContentLength"]),
            content_type=response.get("ContentType"),
        )

    def sha256(self, key: str) -> str:
        digest = hashlib.sha256()
        with self._client.get_object(Bucket=self._bucket, Key=key)["Body"] as body:
            for chunk in body.iter_chunks(chunk_size=64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def ping(self) -> None:
        self._client.head_bucket(Bucket=self._bucket)
