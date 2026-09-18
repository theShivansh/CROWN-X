"""The ingestion worker against fakes: stages, failures, idempotency and the Lambda routing."""

from __future__ import annotations

import io

import pytest

from crownx.app.ingest import handle
from crownx.domain.models import DocumentStatus

BRIEF = (
    "# FestPass project brief\n\n"
    "Faculty coordinator: Prof. Meera Kulkarni, Innovation Cell.\n\n"
    "## Timeline\n\n"
    "Final submissions close on 20 September 2026.\n\n"
    "## Budget\n\n"
    "Budget cap: ₹50,000 (Innovation Cell grant).\n"
).encode()


def test_a_document_moves_through_its_stages_to_ready(api):
    ws = api.new_workspace()
    doc = api.upload(ws, "project-brief-v1.md", BRIEF)

    document = api.store.get_document(ws, doc)
    assert document.status is DocumentStatus.READY
    assert document.error is None
    assert document.chunk_count == len(api.index.chunks) >= 1
    chunk = api.index.chunks[f"{doc}:0"]
    assert chunk["workspace_id"] == ws and chunk["document_id"] == doc
    assert chunk["uploaded_at"] == document.uploaded_at
    assert len(chunk["embedding"]) == api.embedder.dimensions
    text = BRIEF.decode()
    for stored in api.index.chunks.values():
        assert text[stored["char_start"] : stored["char_end"]] == stored["text"]


def test_running_the_worker_twice_leaves_one_set_of_chunks(api):
    ws = api.new_workspace()
    doc = api.upload(ws, "brief.md", BRIEF)
    first = dict(api.index.chunks)

    # A second delivery of the same event, after success: nothing changes.
    api.worker.ingest(ws, doc)
    assert api.index.chunks == first

    # A retry that starts over (as after a crash mid-way) rewrites the same IDs.
    stuck = api.store.get_document(ws, doc).model_copy(update={"status": DocumentStatus.QUEUED})
    api.store.put_document(stuck)
    api.worker.ingest(ws, doc)
    assert sorted(api.index.chunks) == sorted(first)
    assert api.store.get_document(ws, doc).status is DocumentStatus.READY


def test_non_utf8_text_fails_with_an_actionable_reason(api):
    ws = api.new_workspace()
    doc = api.upload(ws, "notes.txt", b"\xff\xfe\x00caf\xe9")
    document = api.store.get_document(ws, doc)
    assert document.status is DocumentStatus.FAILED
    assert document.stage is DocumentStatus.PARSING
    assert "UTF-8" in document.error
    assert api.index.chunks == {}


def test_whitespace_only_text_fails_instead_of_indexing_nothing(api):
    ws = api.new_workspace()
    doc = api.upload(ws, "blank.md", b" \n\n\t\n")
    document = api.store.get_document(ws, doc)
    assert document.status is DocumentStatus.FAILED
    assert "No text found" in document.error


def test_an_indexing_error_marks_the_document_failed_and_re_raises_for_retry(api):
    ws = api.new_workspace()
    doc = api.upload(ws, "brief.md", BRIEF, ingest=False)
    api.index.fail_index = True
    with pytest.raises(ConnectionError):
        api.worker.ingest(ws, doc)
    document = api.store.get_document(ws, doc)
    assert document.status is DocumentStatus.FAILED
    assert document.stage is DocumentStatus.INDEXING
    assert "bulk failed" not in document.error

    api.index.fail_index = False
    api.worker.ingest(ws, doc)  # Lambda's retry succeeds
    assert api.store.get_document(ws, doc).status is DocumentStatus.READY


def test_pending_and_duplicate_documents_are_not_ingested(api):
    ws = api.new_workspace()
    _, body, _ = api.call(
        "POST", f"/workspaces/{ws}/documents/upload-url", {"filename": "a.md", "size_bytes": 5}
    )
    pending = body["document"]["document_id"]
    assert api.worker.ingest(ws, pending).status is DocumentStatus.PENDING
    assert api.index.chunks == {}
    assert api.worker.ingest(ws, "doc_" + "Z" * 22) is None


def test_handler_routes_ensure_index_and_ingest(api):
    api.index.exists = False
    assert handle({"action": "ensure_index"}, api.worker) == {"status": "ok", "created": True}
    assert api.index.created_with["mappings"]["properties"]["embedding"]["dimension"] == 32
    assert handle({"action": "ensure_index"}, api.worker)["created"] is False

    ws = api.new_workspace()
    doc = api.upload(ws, "brief.md", BRIEF, ingest=False)
    result = handle({"action": "ingest", "workspace_id": ws, "document_id": doc}, api.worker)
    assert result == {"status": "ready"}

    with pytest.raises(ValueError):
        handle({"action": "delete_everything"}, api.worker)


def _pdf(pages: list[str] | None) -> bytes:
    """A text PDF with these pages, or (None) one blank page with no text layer."""
    from fpdf import FPDF
    from pypdf import PdfWriter

    if pages is None:
        writer, buffer = PdfWriter(), io.BytesIO()
        writer.add_blank_page(width=595, height=842)
        writer.write(buffer)
        return buffer.getvalue()
    pdf = FPDF()
    pdf.set_font("helvetica", size=11)
    for page in pages:
        pdf.add_page()
        pdf.multi_cell(0, 6, page)
    return bytes(pdf.output())


def test_a_pdf_is_indexed_page_by_page_with_its_header_metadata(api):
    ws = api.new_workspace()
    doc = api.upload(
        ws,
        "brief.pdf",
        _pdf(
            [
                "FestPass project brief - Version: v1 - Date: 31 August 2026",
                "Final submissions close on 20 September 2026.",
            ]
        ),
    )
    document = api.store.get_document(ws, doc)
    assert document.status is DocumentStatus.READY, document.error
    assert (document.version_label, document.source_timestamp) == ("v1", "2026-08-31")
    chunks = sorted(api.index.chunks.values(), key=lambda c: c["chunk_id"])
    assert [c["page_or_section"] for c in chunks] == ["Page 1", "Page 2"]
    assert "20 September 2026" in chunks[1]["text"]
    assert all(c["version_label"] == "v1" for c in chunks)
    assert all(c["source_timestamp"] == "2026-08-31" for c in chunks)


def test_a_pdf_without_text_fails_with_the_srs_reason_and_indexes_nothing(api):
    ws = api.new_workspace()
    doc = api.upload(ws, "scan.pdf", _pdf(None))
    document = api.store.get_document(ws, doc)
    assert document.status is DocumentStatus.FAILED
    assert document.error.startswith("No text found; upload a text PDF.")
    assert api.index.chunks == {}
    assert api.embedder.calls == []


def test_a_corrupt_pdf_fails_with_an_actionable_reason(api):
    ws = api.new_workspace()
    doc = api.upload(ws, "broken.pdf", b"%PDF-1.4 this is not really a pdf")
    document = api.store.get_document(ws, doc)
    assert document.status is DocumentStatus.FAILED
    assert "couldn't be read" in document.error


def test_markdown_header_metadata_reaches_the_document_and_every_chunk(api):
    ws = api.new_workspace()
    doc = api.upload(
        ws, "notes.md", b"Team Lantern - Sync 5 - Friday, 11 September 2026\n\n# Notes\n\nText."
    )
    document = api.store.get_document(ws, doc)
    assert (document.version_label, document.source_timestamp) == ("Sync 5", "2026-09-11")
    assert {c["source_timestamp"] for c in api.index.chunks.values()} == {"2026-09-11"}


def test_the_demo_pdf_is_indexed_with_single_spaced_words(api):
    """pypdf returns this PDF's words separated by two spaces; quotes must read as written."""
    from pathlib import Path

    pdf = Path(__file__).resolve().parents[3] / "demo/documents/workspace-a/project-brief-v1.pdf"
    ws = api.new_workspace()
    doc = api.upload(ws, "project-brief-v1.pdf", pdf.read_bytes())
    document = api.store.get_document(ws, doc)
    assert document.status is DocumentStatus.READY, document.error
    text = " ".join(c["text"] for c in api.index.chunks.values())
    assert "still run on paper forms and group-chat polls" in text
    assert "  " not in text
