"""DynamoDB single-table metadata store. Every key condition names the workspace (SECURITY T2)."""

from __future__ import annotations

import json
from typing import Any

from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from crownx.domain.claims import Claim
from crownx.domain.events import WorkflowEvent
from crownx.domain.models import Document, DocumentStatus, QueryRecord, Workspace, utc_now


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

    def put_query(self, record: QueryRecord) -> None:
        # The evidence snapshot is stored as JSON text: it keeps float scores exact (DynamoDB would
        # need Decimals) and makes the record's immutability obvious.
        fields = record.model_dump(mode="json", exclude={"evidence", "conflicts"})
        self._table.put_item(
            Item={
                "PK": _ws(record.workspace_id),
                "SK": f"QUERY#{record.query_id}",
                **{k: v for k, v in fields.items() if v is not None},
                "evidence_json": json.dumps(record.evidence, ensure_ascii=False),
                "conflicts_json": json.dumps(record.conflicts, ensure_ascii=False),
            },
            ConditionExpression=Attr("PK").not_exists(),
        )

    def get_query(self, workspace_id: str, query_id: str) -> QueryRecord | None:
        item = self._table.get_item(
            Key={"PK": _ws(workspace_id), "SK": f"QUERY#{query_id}"}, ConsistentRead=True
        ).get("Item")
        if not item:
            return None
        fields = _strip_keys(item)
        fields["evidence"] = json.loads(fields.pop("evidence_json"))
        fields["conflicts"] = json.loads(fields.pop("conflicts_json", "[]"))
        fields["retrieval_ms"] = int(fields.get("retrieval_ms", 0))
        return QueryRecord.model_validate(fields)

    def put_audit(self, workspace_id: str, event: dict) -> None:
        self._table.put_item(
            Item={
                "PK": _ws(workspace_id),
                "SK": f"AUDIT#{event['timestamp']}#{event['request_id']}",
                "event_json": json.dumps(event),
                "event_type": event["event_type"],
            }
        )

    def put_event(self, event: WorkflowEvent) -> None:
        """Append-only and idempotent: writing the same event twice leaves one item."""
        try:
            self._table.put_item(
                Item={
                    "PK": _ws(event.workspace_id),
                    "SK": f"EVENT#{event.occurred_at}#{event.event_id}",
                    "event_json": event.model_dump_json(),
                    "event_type": event.event_type.value,
                },
                ConditionExpression=Attr("SK").not_exists(),
            )
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

    def list_events(self, workspace_id: str, limit: int = 2000) -> list[WorkflowEvent]:
        """The newest `limit` events, oldest first."""
        response = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={":pk": _ws(workspace_id), ":prefix": "EVENT#"},
            ScanIndexForward=False,
            Limit=limit,
        )
        events = [WorkflowEvent.model_validate_json(i["event_json"]) for i in response["Items"]]
        return sorted(events, key=lambda e: (e.occurred_at, e.event_id))

    def replace_claims(self, workspace_id: str, document_id: str, claims: list[Claim]) -> None:
        stale = [
            item["SK"]
            for item in self._query_prefix(workspace_id, "CLAIM#")
            if item.get("document_id") == document_id
        ]
        with self._table.batch_writer() as batch:
            for sk in stale:
                batch.delete_item(Key={"PK": _ws(workspace_id), "SK": sk})
            for claim in claims:
                batch.put_item(
                    Item={
                        "PK": _ws(workspace_id),
                        "SK": f"CLAIM#{claim.subject}#{claim.attribute}#{claim.claim_id}",
                        "document_id": claim.document_id,
                        # JSON text keeps the confidence float exact (DynamoDB wants Decimals).
                        "claim_json": claim.model_dump_json(),
                    }
                )

    def list_claims(self, workspace_id: str) -> list[Claim]:
        return [
            Claim.model_validate_json(item["claim_json"])
            for item in self._query_prefix(workspace_id, "CLAIM#")
        ]

    def _query_prefix(self, workspace_id: str, prefix: str) -> list[dict]:
        paginator = self._client.get_paginator("query")
        pages = paginator.paginate(
            TableName=self._table.name,
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            # A resource's client serializes plain values, as in `list_documents`.
            ExpressionAttributeValues={":pk": _ws(workspace_id), ":prefix": prefix},
            ConsistentRead=True,
        )
        return [item for page in pages for item in page["Items"]]


def _document_item(document: Document) -> dict:
    fields = {k: v for k, v in document.model_dump(mode="json").items() if v is not None}
    return {"PK": _ws(document.workspace_id), "SK": f"DOC#{document.document_id}", **fields}


def _strip_keys(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in ("PK", "SK")}
