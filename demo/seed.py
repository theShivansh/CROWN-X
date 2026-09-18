"""Seed the demo workspaces through the public API, exactly as the browser does.

Creates workspace A ("Team Lantern · FestPass") and workspace B ("Team Tiffin · MessMate"), uploads the
corpus in the order docs/SCENARIO.md §2 fixes (the owner conflict's selection depends on it), confirms
each upload, and waits for every document to reach `ready` or `failed`. Prints the workspace IDs as
JSON; record them in docs/PROGRESS.md.

    python demo/seed.py --api https://<api-id>.execute-api.ap-south-1.amazonaws.com
    python demo/seed.py --api ... --subset video     # D1, D3, D4 only (SCENARIO.md §9)

Standard library only, so it runs anywhere Python 3.11+ does.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

DOCS = Path(__file__).resolve().parent / "documents"

# SCENARIO.md §2 upload order: D1, D2, D6, D3, D4, D5.
WORKSPACE_A = [
    "project-brief-v1.pdf",
    "api-limits-spec-v1.md",
    "team-roles.md",
    "organiser-update-3.txt",
    "meeting-notes-sync-5.md",
    "budget-sheet-v2.md",
]
VIDEO_SUBSET = ["project-brief-v1.pdf", "organiser-update-3.txt", "meeting-notes-sync-5.md"]
WORKSPACE_B = ["messmate-brief-v2.md"]
SETTLED = {"ready", "failed", "duplicate"}


def call(api: str, method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        f"{api.rstrip('/')}{path}",
        data=data,
        method=method,
        headers={"content-type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise SystemExit(f"{method} {path} failed with HTTP {error.code}: {detail}") from error


def post_to_s3(upload: dict, filename: str, content: bytes) -> None:
    """Multipart form POST with the pre-signed fields first and the file last, as S3 requires."""
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in upload["fields"].items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {upload['fields'].get('Content-Type', 'application/octet-stream')}\r\n\r\n".encode()
        + content
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        upload["url"],
        data=b"".join(parts),
        method="POST",
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.status not in (200, 201, 204):
            raise SystemExit(f"S3 rejected {filename}: HTTP {response.status}")


def upload(api: str, workspace_id: str, folder: Path, filename: str) -> str:
    content = (folder / filename).read_bytes()
    ticket = call(
        api,
        "POST",
        f"/workspaces/{workspace_id}/documents/upload-url",
        {"filename": filename, "size_bytes": len(content)},
    )
    post_to_s3(ticket["upload"], filename, content)
    document_id = ticket["document"]["document_id"]
    call(api, "POST", f"/workspaces/{workspace_id}/documents/{document_id}/complete")
    print(f"  uploaded {filename} as {document_id}", file=sys.stderr)
    return document_id


def wait(api: str, workspace_id: str, timeout_s: int) -> list[dict]:
    deadline = time.monotonic() + timeout_s
    while True:
        documents = call(api, "GET", f"/workspaces/{workspace_id}/documents")["documents"]
        if all(d["status"] in SETTLED for d in documents) or time.monotonic() > deadline:
            return documents
        time.sleep(2)


def seed(api: str, folder: Path, filenames: list[str], timeout_s: int) -> dict:
    workspace_id = call(api, "POST", "/workspaces")["workspace"]["workspace_id"]
    print(f"workspace {workspace_id}", file=sys.stderr)
    for filename in filenames:
        upload(api, workspace_id, folder, filename)
        # Settle each document before the next, so `uploaded_at` order is the scenario's order.
        wait(api, workspace_id, timeout_s)
    documents = wait(api, workspace_id, timeout_s)
    return {
        "workspace_id": workspace_id,
        "documents": [
            {k: d.get(k) for k in ("filename", "document_id", "status", "chunk_count", "error")}
            for d in documents
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the CROWN-X demo workspaces.")
    parser.add_argument("--api", required=True, help="API base URL (the stack's ApiUrl output)")
    parser.add_argument("--subset", choices=["all", "video"], default="all")
    parser.add_argument("--timeout", type=int, default=180, help="seconds to wait per document")
    args = parser.parse_args()

    result = {
        "workspace_a": seed(
            args.api,
            DOCS / "workspace-a",
            VIDEO_SUBSET if args.subset == "video" else WORKSPACE_A,
            args.timeout,
        )
    }
    if args.subset == "all":
        result["workspace_b"] = seed(args.api, DOCS / "workspace-b", WORKSPACE_B, args.timeout)
    print(json.dumps(result, indent=2))
    failed = [d for ws in result.values() for d in ws["documents"] if d["status"] != "ready"]
    if failed:
        raise SystemExit(f"{len(failed)} document(s) did not reach ready; see the output above")


if __name__ == "__main__":
    main()
