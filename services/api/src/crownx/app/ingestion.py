"""The ingestion worker: object -> text -> chunks -> embeddings -> index, with visible stages.

Safe to run twice for one document: chunk IDs are `{document_id}:{ordinal}` and are written by ID, a
ready document is left alone, and every status change is conditional on the status just read.
"""

from __future__ import annotations

import logging

from crownx.adapters.ports import Embedder, MetadataStore, ObjectStore, SearchIndex
from crownx.domain.chunking import chunk_text, normalize_text
from crownx.domain.models import Document, DocumentStatus
from crownx.domain.retrieval import index_body

log = logging.getLogger(__name__)

PROCESSABLE = {
    DocumentStatus.QUEUED,
    DocumentStatus.PARSING,
    DocumentStatus.INDEXING,
    DocumentStatus.FAILED,
}


class IngestionWorker:
    def __init__(
        self,
        store: MetadataStore,
        objects: ObjectStore,
        embedder: Embedder,
        index: SearchIndex,
        target_chars: int = 1000,
        overlap_chars: int = 120,
    ) -> None:
        self._store = store
        self._objects = objects
        self._embedder = embedder
        self._index = index
        self._target_chars = target_chars
        self._overlap_chars = overlap_chars

    def ensure_index(self) -> bool:
        return self._index.ensure_index(index_body(self._embedder.dimensions))

    def ingest(self, workspace_id: str, document_id: str) -> Document | None:
        document = self._store.get_document(workspace_id, document_id)
        if document is None or document.status not in PROCESSABLE:
            return document  # unknown, still pending, duplicate or already ready: nothing to do

        document = self._advance(document, DocumentStatus.PARSING)
        if document is None:
            return None  # another run moved it first
        try:
            raw = self._objects.read_bytes(document.object_key)
            try:
                text = normalize_text(raw.decode("utf-8"))
            except UnicodeDecodeError:
                return self._fail(
                    document, "The file isn't UTF-8 text. Save it as UTF-8 and upload it again."
                )
            chunks = chunk_text(text, self._target_chars, self._overlap_chars)
            if not chunks:
                return self._fail(
                    document, "No text found in the file. Upload a file with some text in it."
                )

            document = self._advance(document, DocumentStatus.INDEXING)
            if document is None:
                return None
            self._index.ensure_index(index_body(self._embedder.dimensions))
            vectors = self._embedder.embed([chunk.text for chunk in chunks])
            self._index.index_chunks(
                [
                    {
                        "chunk_id": f"{document.document_id}:{chunk.ordinal}",
                        "workspace_id": document.workspace_id,
                        "document_id": document.document_id,
                        "text": chunk.text,
                        "page_or_section": chunk.section,
                        "char_start": chunk.char_start,
                        "char_end": chunk.char_end,
                        "version_label": document.version_label,
                        "source_timestamp": document.source_timestamp,
                        "uploaded_at": document.uploaded_at,
                        "embedding": vector,
                    }
                    for chunk, vector in zip(chunks, vectors, strict=True)
                ]
            )
            return self._advance(document, DocumentStatus.READY, chunk_count=len(chunks))
        except Exception:
            log.exception("ingestion failed at stage %s", document.status)
            self._fail(
                document,
                "Indexing failed on our side. Upload the file again; if it keeps failing, "
                "the logs have the details under this document ID.",
            )
            raise  # let Lambda's async retry run the (idempotent) worker again

    def _advance(
        self, document: Document, status: DocumentStatus, **changes: object
    ) -> Document | None:
        updated = document.model_copy(
            update={"status": status, "stage": status, "error": None, **changes}
        )
        return updated if self._store.replace_document(updated, document.status) else None

    def _fail(self, document: Document, reason: str) -> Document:
        failed = document.model_copy(
            update={"status": DocumentStatus.FAILED, "stage": document.status, "error": reason}
        )
        self._store.replace_document(failed, document.status)
        return failed
