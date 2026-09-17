"""DynamoDB single-table metadata store. Every key condition names the workspace (SECURITY T2)."""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Attr

from crownx.domain.models import Document, DocumentStatus, Workspace, utc_now


def _ws(workspace_id: str) -> str:
    return f"WS#{workspace_id}"


class DynamoMetadataStore:
    def __init__(self, table: Any) -> None:
        self._table = table  # boto3.resource("dynamodb").Table(name)
        self._client = table.meta.client

    def put_workspace(self, workspace: Workspace) -> None:
        self._table.put_item(
            Item={"PK": _ws(workspace.workspace_id), "SK": "META", **workspace.model_dump()},
            ConditionExpression=Attr("PK").not_exists(),
        )

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        item = self._table.get_item(Key={"PK": _ws(workspace_id), "SK": "META"}).get("Item")
        return Workspace.model_validate(_strip_keys(item)) if item else None

    def put_document(self, document: Document) -> None:
        self._table.put_item(Item=_document_item(document))

    def get_document(self, workspace_id: str, document_id: str) -> Document | None:
        item = self._table.get_item(Key={"PK": _ws(workspace_id), "SK": f"DOC#{document_id}"}).get(
            "Item"
        )
        return Document.model_validate(_strip_keys(item)) if item else None

    def list_documents(self, workspace_id: str) -> list[Document]:
        paginator = self._client.get_paginator("query")
        pages = paginator.paginate(
            TableName=self._table.name,
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={":pk": _ws(workspace_id), ":prefix": "DOC#"},
        )
        documents = [
            Document.model_validate(_strip_keys(item)) for page in pages for item in page["Items"]
        ]
        return sorted(documents, key=lambda d: d.uploaded_at)

    def replace_document(self, document: Document, expected_status: DocumentStatus) -> bool:
        try:
            self._table.put_item(
                Item=_document_item(document),
                ConditionExpression=Attr("status").eq(expected_status.value),
            )
        except self._client.exceptions.ConditionalCheckFailedException:
            return False  # another request moved it on first; the caller re-reads
        return True

    def claim_checksum(self, workspace_id: str, checksum: str, document_id: str) -> str:
        key = {"PK": _ws(workspace_id), "SK": f"CHECKSUM#{checksum}"}
        try:
            self._table.put_item(
                Item={**key, "document_id": document_id, "created_at": utc_now()},
                ConditionExpression=Attr("PK").not_exists(),
            )
        except self._client.exceptions.ConditionalCheckFailedException:
            item = self._table.get_item(Key=key, ConsistentRead=True)["Item"]
            return str(item["document_id"])
        return document_id


def _document_item(document: Document) -> dict:
    fields = {k: v for k, v in document.model_dump(mode="json").items() if v is not None}
    return {"PK": _ws(document.workspace_id), "SK": f"DOC#{document.document_id}", **fields}


def _strip_keys(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in ("PK", "SK")}
