"""Workspace and document use cases, written against ports so tests run without AWS."""

from __future__ import annotations

from dataclasses import dataclass

from crownx.adapters.ports import IngestQueue, MetadataStore, ObjectStore, SearchIndex
from crownx.domain.errors import LimitReached, NotFound, TooLarge, UploadIncomplete
from crownx.domain.ids import is_document_id, is_workspace_id, new_document_id, new_workspace_id
from crownx.domain.models import Document, DocumentStatus, Workspace, utc_now
from crownx.domain.uploads import object_key, validate_upload


@dataclass(frozen=True)
class Limits:
    max_upload_bytes: int
    max_documents_per_workspace: int
    upload_url_expiry_seconds: int


@dataclass(frozen=True)
class UploadTicket:
    document: Document
    upload: dict
    expires_in: int


@dataclass(frozen=True)
class Completion:
    document: Document
    duplicate: bool


class CrownService:
    def __init__(
        self,
        store: MetadataStore,
        objects: ObjectStore,
        ingest: IngestQueue,
        index: SearchIndex,
        limits: Limits,
    ) -> None:
        self._store = store
        self._objects = objects
        self._ingest = ingest
        self._index = index
        self._limits = limits

    # Workspaces ---------------------------------------------------------------------------------

    def create_workspace(self) -> Workspace:
        workspace = Workspace(workspace_id=new_workspace_id(), created_at=utc_now())
        self._store.put_workspace(workspace)
        return workspace

    def require_workspace(self, workspace_id: str) -> Workspace:
        workspace = (
            self._store.get_workspace(workspace_id) if is_workspace_id(workspace_id) else None
        )
        if workspace is None:
            raise NotFound("Workspace not found. Check the link, or create a new workspace.")
        return workspace

    # Documents ----------------------------------------------------------------------------------

    def create_upload(self, workspace_id: str, filename: str, size_bytes: int) -> UploadTicket:
        self.require_workspace(workspace_id)
        spec = validate_upload(filename, size_bytes, self._limits.max_upload_bytes)
        if (
            len(self._store.list_documents(workspace_id))
            >= self._limits.max_documents_per_workspace
        ):
            raise LimitReached(
                f"This workspace already holds {self._limits.max_documents_per_workspace} "
                "documents, the limit for the demo. Start a new workspace to upload more."
            )
        document_id = new_document_id()
        document = Document(
            document_id=document_id,
            workspace_id=workspace_id,
            filename=spec.filename,
            content_type=spec.content_type,
            size_bytes=spec.size_bytes,
            object_key=object_key(workspace_id, document_id, spec.filename),
            status=DocumentStatus.PENDING,
            stage=DocumentStatus.PENDING,
            uploaded_at=utc_now(),
        )
        self._store.put_document(document)
        expires_in = self._limits.upload_url_expiry_seconds
        upload = self._objects.presigned_post(
            document.object_key, spec.content_type, self._limits.max_upload_bytes, expires_in
        )
        return UploadTicket(document=document, upload=upload, expires_in=expires_in)

    def complete_upload(self, workspace_id: str, document_id: str) -> Completion:
        document = self.require_document(workspace_id, document_id)
        if document.status is not DocumentStatus.PENDING:
            return self._settled(document)  # a repeated call changes nothing

        info = self._objects.head(document.object_key)
        if info is None:
            raise UploadIncomplete(
                "The file hasn't reached storage yet. Finish the upload, then confirm it again."
            )
        if info.size_bytes > self._limits.max_upload_bytes:
            raise TooLarge(
                f"The stored file is {info.size_bytes:,} bytes; the limit is "
                f"{self._limits.max_upload_bytes:,} bytes."
            )

        checksum = self._objects.sha256(document.object_key)
        owner = self._store.claim_checksum(workspace_id, checksum, document_id)
        if owner != document_id:
            duplicate = document.model_copy(
                update={
                    "status": DocumentStatus.DUPLICATE,
                    "stage": DocumentStatus.DUPLICATE,
                    "checksum": checksum,
                    "size_bytes": info.size_bytes,
                    "duplicate_of": owner,
                }
            )
            if not self._store.replace_document(duplicate, DocumentStatus.PENDING):
                return self._settled(self.require_document(workspace_id, document_id))
            return Completion(document=self.require_document(workspace_id, owner), duplicate=True)

        queued = document.model_copy(
            update={
                "status": DocumentStatus.QUEUED,
                "stage": DocumentStatus.QUEUED,
                "checksum": checksum,
                "size_bytes": info.size_bytes,
            }
        )
        if not self._store.replace_document(queued, DocumentStatus.PENDING):
            return self._settled(self.require_document(workspace_id, document_id))
        self._ingest.enqueue(workspace_id, document_id)
        return Completion(document=queued, duplicate=False)

    def list_documents(self, workspace_id: str) -> list[Document]:
        self.require_workspace(workspace_id)
        return self._store.list_documents(workspace_id)

    def require_document(self, workspace_id: str, document_id: str) -> Document:
        self.require_workspace(workspace_id)
        document = (
            self._store.get_document(workspace_id, document_id)
            if is_document_id(document_id)
            else None
        )
        if document is None:
            raise NotFound("Document not found in this workspace.")
        return document

    def _settled(self, document: Document) -> Completion:
        if document.status is DocumentStatus.DUPLICATE and document.duplicate_of:
            original = self.require_document(document.workspace_id, document.duplicate_of)
            return Completion(document=original, duplicate=True)
        return Completion(document=document, duplicate=False)

    # Health -------------------------------------------------------------------------------------

    def health(self) -> dict[str, str]:
        """Per-dependency status. Never includes names, endpoints or error text."""
        checks: dict[str, str] = {"config": "ok"}
        try:
            self._store.get_workspace("ws_health-check-000000000")
            checks["table"] = "ok"
        except Exception:  # noqa: BLE001  # reported as a status, not raised
            checks["table"] = "unreachable"
        try:
            self._objects.ping()
            checks["bucket"] = "ok"
        except Exception:  # noqa: BLE001
            checks["bucket"] = "unreachable"
        try:
            checks["index"] = "ok" if self._index.index_exists() else "missing"
        except Exception:  # noqa: BLE001
            checks["index"] = "unreachable"
        return checks
