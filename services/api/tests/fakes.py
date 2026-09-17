"""In-memory doubles of the ports in `crownx.adapters.ports`. They live only under tests/."""

from __future__ import annotations

import hashlib

from crownx.adapters.ports import ObjectInfo
from crownx.domain.models import Document, DocumentStatus, Workspace


class FakeStore:
    def __init__(self) -> None:
        self.workspaces: dict[str, Workspace] = {}
        self.documents: dict[tuple[str, str], Document] = {}
        self.checksums: dict[tuple[str, str], str] = {}
        self.fail = False

    def _check(self) -> None:
        if self.fail:
            raise ConnectionError("table unreachable")

    def put_workspace(self, workspace: Workspace) -> None:
        self._check()
        self.workspaces[workspace.workspace_id] = workspace

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        self._check()
        return self.workspaces.get(workspace_id)

    def put_document(self, document: Document) -> None:
        self.documents[(document.workspace_id, document.document_id)] = document

    def get_document(self, workspace_id: str, document_id: str) -> Document | None:
        return self.documents.get((workspace_id, document_id))

    def list_documents(self, workspace_id: str) -> list[Document]:
        found = [d for (ws, _), d in self.documents.items() if ws == workspace_id]
        return sorted(found, key=lambda d: d.uploaded_at)

    def replace_document(self, document: Document, expected_status: DocumentStatus) -> bool:
        key = (document.workspace_id, document.document_id)
        current = self.documents.get(key)
        if current is None or current.status is not expected_status:
            return False
        self.documents[key] = document
        return True

    def claim_checksum(self, workspace_id: str, checksum: str, document_id: str) -> str:
        return self.checksums.setdefault((workspace_id, checksum), document_id)


class FakeObjects:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.posts: list[dict] = []
        self.fail_ping = False

    def presigned_post(self, key: str, content_type: str, max_bytes: int, expires_in: int) -> dict:
        self.posts.append(
            {
                "key": key,
                "content_type": content_type,
                "max_bytes": max_bytes,
                "expires_in": expires_in,
            }
        )
        return {
            "url": "https://documents.example.test/",
            "fields": {"key": key, "Content-Type": content_type},
        }

    def head(self, key: str) -> ObjectInfo | None:
        data = self.objects.get(key)
        return None if data is None else ObjectInfo(size_bytes=len(data), content_type=None)

    def sha256(self, key: str) -> str:
        return hashlib.sha256(self.objects[key]).hexdigest()

    def ping(self) -> None:
        if self.fail_ping:
            raise ConnectionError("bucket unreachable")


class FakeIngest:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, str]] = []

    def enqueue(self, workspace_id: str, document_id: str) -> None:
        self.enqueued.append((workspace_id, document_id))


class FakeIndex:
    def __init__(self) -> None:
        self.exists = True
        self.error: Exception | None = None

    def index_exists(self) -> bool:
        if self.error:
            raise self.error
        return self.exists
