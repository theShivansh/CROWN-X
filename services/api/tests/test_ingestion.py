"""The ingestion worker against fakes: stages, failures, idempotency and the Lambda routing."""

from __future__ import annotations

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
