"""The HTTP API against fake adapters: contracts, errors and workspace isolation."""

from __future__ import annotations

from conftest import MAX_BYTES, MAX_DOCS

REQUEST_ID = "req_Tst123abc="


def new_workspace(api) -> str:
    status, body, _ = api.call("POST", "/workspaces")
    assert status == 201
    return body["workspace"]["workspace_id"]


def start_upload(api, ws: str, filename: str = "brief.md", size: int = 100) -> dict:
    status, body, _ = api.call(
        "POST", f"/workspaces/{ws}/documents/upload-url", {"filename": filename, "size_bytes": size}
    )
    assert status == 201, body
    return body


def assert_error(result, status: int, code: str) -> None:
    got_status, body, headers = result
    assert got_status == status, body
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["request_id"] == REQUEST_ID
    assert body["error"]["message"]
    assert headers.get("x-request-id") == REQUEST_ID


def test_create_workspace_returns_an_unguessable_id_and_request_id(api):
    status, body, headers = api.call("POST", "/workspaces")
    assert status == 201
    assert body["workspace"]["workspace_id"].startswith("ws_")
    assert body["request_id"] == REQUEST_ID == headers["x-request-id"]


def test_upload_url_creates_a_pending_document_and_a_size_limited_post(api):
    ws = new_workspace(api)
    body = start_upload(api, ws, "Organiser update.txt", 321)
    document = body["document"]
    assert document["status"] == "pending"
    assert document["filename"] == "Organiser-update.txt"
    assert document["content_type"] == "text/plain"
    assert "object_key" not in document
    assert body["expires_in"] == 300
    assert body["upload"]["fields"]["Content-Type"] == "text/plain"
    post = api.objects.posts[-1]
    assert post["key"] == f"ws/{ws}/{document['document_id']}/Organiser-update.txt"
    assert post["max_bytes"] == MAX_BYTES and post["expires_in"] == 300


def test_upload_url_rejects_wrong_extension_with_400(api):
    ws = new_workspace(api)
    result = api.call(
        "POST",
        f"/workspaces/{ws}/documents/upload-url",
        {"filename": "slides.pptx", "size_bytes": 10},
    )
    assert_error(result, 400, "unsupported_type")
    assert api.store.documents == {}


def test_upload_url_rejects_oversize_declaration_with_413(api):
    ws = new_workspace(api)
    result = api.call(
        "POST",
        f"/workspaces/{ws}/documents/upload-url",
        {"filename": "big.md", "size_bytes": MAX_BYTES + 1},
    )
    assert_error(result, 413, "too_large")


def test_upload_url_enforces_the_document_limit_with_429(api):
    ws = new_workspace(api)
    for n in range(MAX_DOCS):
        start_upload(api, ws, f"doc{n}.md")
    result = api.call(
        "POST",
        f"/workspaces/{ws}/documents/upload-url",
        {"filename": "one-more.md", "size_bytes": 5},
    )
    assert_error(result, 429, "limit_reached")


def test_malformed_bodies_are_400(api):
    ws = new_workspace(api)
    path = f"/workspaces/{ws}/documents/upload-url"
    assert_error(api.call("POST", path, raw_body="{not json"), 400, "invalid_request")
    assert_error(api.call("POST", path, {"filename": "a.md"}), 400, "invalid_request")
    assert_error(
        api.call("POST", path, {"filename": "a.md", "size_bytes": 1, "extra": True}),
        400,
        "invalid_request",
    )


def test_complete_before_the_object_exists_is_409(api):
    ws = new_workspace(api)
    doc = start_upload(api, ws)["document"]["document_id"]
    assert_error(
        api.call("POST", f"/workspaces/{ws}/documents/{doc}/complete"), 409, "upload_incomplete"
    )
    assert api.ingest.enqueued == []


def test_complete_queues_ingestion_once_even_when_repeated(api):
    ws = new_workspace(api)
    doc = start_upload(api, ws)["document"]["document_id"]
    api.objects.objects[api.objects.posts[-1]["key"]] = (
        b"# Brief\nSubmissions close on 20 September 2026.\n"
    )

    status, body, _ = api.call("POST", f"/workspaces/{ws}/documents/{doc}/complete")
    assert status == 200
    assert body["duplicate"] is False
    assert body["document"]["status"] == "queued"
    assert len(body["document"]["checksum"]) == 64

    status, again, _ = api.call("POST", f"/workspaces/{ws}/documents/{doc}/complete")
    assert status == 200 and again["document"]["status"] == "queued"
    assert api.ingest.enqueued == [(ws, doc)]


def test_complete_on_a_known_checksum_returns_the_original(api):
    ws = new_workspace(api)
    content = b"Deadline confirmed as 2026-09-22.\n"
    first = start_upload(api, ws, "notes.md")["document"]["document_id"]
    api.objects.objects[api.objects.posts[-1]["key"]] = content
    api.call("POST", f"/workspaces/{ws}/documents/{first}/complete")

    second = start_upload(api, ws, "notes-copy.md")["document"]["document_id"]
    api.objects.objects[api.objects.posts[-1]["key"]] = content
    status, body, _ = api.call("POST", f"/workspaces/{ws}/documents/{second}/complete")

    assert status == 200
    assert body["duplicate"] is True
    assert body["document"]["document_id"] == first
    assert api.store.get_document(ws, second).duplicate_of == first
    assert api.ingest.enqueued == [(ws, first)]


def test_same_content_in_another_workspace_is_not_a_duplicate(api):
    content = b"Same bytes, two teams.\n"
    for _ in range(2):
        ws = new_workspace(api)
        doc = start_upload(api, ws)["document"]["document_id"]
        api.objects.objects[api.objects.posts[-1]["key"]] = content
        _, body, _ = api.call("POST", f"/workspaces/{ws}/documents/{doc}/complete")
        assert body["duplicate"] is False
    assert len(api.ingest.enqueued) == 2


def test_ids_from_another_workspace_return_404(api):
    ws_a, ws_b = new_workspace(api), new_workspace(api)
    doc_a = start_upload(api, ws_a)["document"]["document_id"]
    assert_error(
        api.call("POST", f"/workspaces/{ws_b}/documents/{doc_a}/complete"), 404, "not_found"
    )
    _, listing, _ = api.call("GET", f"/workspaces/{ws_b}/documents")
    assert listing["documents"] == []


def test_unknown_or_malformed_workspace_ids_return_404(api):
    for ws in ("ws_" + "A" * 22, "ws_short", "not-a-workspace"):
        assert_error(api.call("GET", f"/workspaces/{ws}/documents"), 404, "not_found")
        assert_error(
            api.call(
                "POST",
                f"/workspaces/{ws}/documents/upload-url",
                {"filename": "a.md", "size_bytes": 1},
            ),
            404,
            "not_found",
        )


def test_list_documents_returns_only_this_workspace_in_upload_order(api):
    ws = new_workspace(api)
    names = [start_upload(api, ws, f"d{n}.md")["document"]["filename"] for n in range(3)]
    new_workspace(api)
    status, body, _ = api.call("GET", f"/workspaces/{ws}/documents")
    assert status == 200
    assert [d["filename"] for d in body["documents"]] == names
    assert body["request_id"] == REQUEST_ID


def test_unknown_route_uses_the_envelope(api):
    assert_error(api.call("GET", "/nope"), 404, "not_found")


def test_unexpected_errors_are_500_without_internals(api, monkeypatch):
    def boom():
        raise RuntimeError("table name crownx-secret-internal")

    monkeypatch.setattr(api.service, "create_workspace", boom)
    result = api.call("POST", "/workspaces")
    assert_error(result, 500, "internal_error")
    assert "crownx-secret-internal" not in result[1]["error"]["message"]


def test_health_is_green_when_every_dependency_answers(api):
    status, body, _ = api.call("GET", "/health")
    assert status == 200
    assert body["status"] == "ok"
    assert body["dependencies"] == {"config": "ok", "table": "ok", "bucket": "ok", "index": "ok"}


def test_health_reports_each_failing_dependency_without_details(api):
    api.index.error = ConnectionError("https://search-crownx.example: timeout")
    api.objects.fail_ping = True
    status, body, _ = api.call("GET", "/health")
    assert status == 503
    assert body["status"] == "degraded"
    assert body["dependencies"] == {
        "config": "ok",
        "table": "ok",
        "bucket": "unreachable",
        "index": "unreachable",
    }
    assert "example" not in str(body)


def test_health_treats_a_missing_index_as_degraded(api):
    api.index.exists = False
    status, body, _ = api.call("GET", "/health")
    assert status == 503 and body["dependencies"]["index"] == "missing"


def test_health_reports_invalid_configuration_without_naming_it(api):
    def broken_config():
        raise ValueError("Field required: TABLE_NAME")

    status, body, _ = api.call("GET", "/health", factory=broken_config)
    assert status == 503
    assert body == {
        "status": "degraded",
        "dependencies": {"config": "invalid"},
        "request_id": REQUEST_ID,
    }
