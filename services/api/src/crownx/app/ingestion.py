"""The ingestion worker: object -> text -> chunks -> embeddings -> index, with visible stages.

Safe to run twice for one document: chunk IDs are `{document_id}:{ordinal}` and are written by ID, a
ready document is left alone, and every status change is conditional on the status just read.
"""

from __future__ import annotations

import logging

from crownx.adapters.pdf import UnreadablePdf, read_pdf_pages
from crownx.adapters.ports import Embedder, MetadataStore, ObjectStore, SearchIndex
from crownx.app.events import record_event
from crownx.domain.chunking import Chunk, chunk_pages, chunk_text, normalize_text
from crownx.domain.events import EventType
from crownx.domain.metadata import extract_metadata
from crownx.domain.models import Document, DocumentStatus
from crownx.domain.retrieval import EmbeddingNamespace, index_body

log = logging.getLogger(__name__)

PDF = "application/pdf"
NO_TEXT_IN_PDF = (
    "No text found; upload a text PDF. This one has no text layer, as happens with scanned pages."
)

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
        namespace: EmbeddingNamespace,
        target_chars: int = 1000,
        overlap_chars: int = 120,
    ) -> None:
        self._store = store
        self._objects = objects
        self._embedder = embedder
        self._index = index
        self._namespace = namespace
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
            parsed = self._parse(document, raw)
            if isinstance(parsed, str):
                return self._fail(document, parsed)
            text, chunks = parsed
            if not chunks:
                return self._fail(
                    document,
                    NO_TEXT_IN_PDF
                    if document.content_type == PDF
                    else "No text found in the file. Upload a file with some text in it.",
                )

            metadata = extract_metadata(text)
            document = self._advance(
                document,
                DocumentStatus.INDEXING,
                version_label=metadata.version_label,
                source_timestamp=metadata.source_timestamp,
            )
            if document is None:
                return None
            self._index.ensure_index(index_body(self._embedder.dimensions))
            vectors = self._embedder.embed([chunk.text for chunk in chunks], kind="passage")
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
                        **self._namespace.fields(),
                    }
                    for chunk, vector in zip(chunks, vectors, strict=True)
                ]
            )
            ready = self._advance(document, DocumentStatus.READY, chunk_count=len(chunks))
            if ready is not None:
                record_event(
                    self._store,
                    ready.workspace_id,
                    EventType.DOCUMENT_INDEXED,
                    document_id=ready.document_id,
                    chunk_count=len(chunks),
                )
            return ready
        except Exception:
            log.exception("ingestion failed at stage %s", document.status)
            self._fail(
                document,
                "Indexing failed on our side. Upload the file again; if it keeps failing, "
                "the logs have the details under this document ID.",
            )
            raise  # let Lambda's async retry run the (idempotent) worker again

    def _parse(self, document: Document, raw: bytes) -> tuple[str, list[Chunk]] | str:
        """The text and its chunks, or the failure reason the user sees."""
        if document.content_type == PDF:
            try:
                pages = read_pdf_pages(raw)
            except UnreadablePdf:
                return "The PDF couldn't be read. Export it again as a standard PDF and upload it."
            return chunk_pages(pages, self._target_chars, self._overlap_chars)
        try:
            text = normalize_text(raw.decode("utf-8"))
        except UnicodeDecodeError:
            return "The file isn't UTF-8 text. Save it as UTF-8 and upload it again."
        return text, chunk_text(text, self._target_chars, self._overlap_chars)

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
        if self._store.replace_document(failed, document.status):
            record_event(
                self._store,
                failed.workspace_id,
                EventType.DOCUMENT_FAILED,
                document_id=failed.document_id,
                stage=str(document.status),
            )
        return failed
