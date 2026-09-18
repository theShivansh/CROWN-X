"""In-memory doubles of the ports in `crownx.adapters.ports`. They live only under tests/."""

from __future__ import annotations

import hashlib
import math
import re

from crownx.adapters.ports import AnswerResult, ObjectInfo, SearchHit
from crownx.domain.answering import AnswerDraft
from crownx.domain.models import Document, DocumentStatus, QueryRecord, Workspace


class FakeStore:
    def __init__(self) -> None:
        self.workspaces: dict[str, Workspace] = {}
        self.documents: dict[tuple[str, str], Document] = {}
        self.checksums: dict[tuple[str, str], str] = {}
        self.queries: dict[tuple[str, str], QueryRecord] = {}
        self.audit: list[tuple[str, dict]] = []
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

    def put_query(self, record: QueryRecord) -> None:
        key = (record.workspace_id, record.query_id)
        assert key not in self.queries, "query records are written once"
        self.queries[key] = record

    def get_query(self, workspace_id: str, query_id: str) -> QueryRecord | None:
        return self.queries.get((workspace_id, query_id))

    def put_audit(self, workspace_id: str, event: dict) -> None:
        self.audit.append((workspace_id, dict(event)))


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

    def read_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def ping(self) -> None:
        if self.fail_ping:
            raise ConnectionError("bucket unreachable")


class FakeIngest:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, str]] = []

    def enqueue(self, workspace_id: str, document_id: str) -> None:
        self.enqueued.append((workspace_id, document_id))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class FakeEmbedder:
    """Deterministic bag-of-words vectors: texts sharing words point the same way."""

    dimensions = 32

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.error: Exception | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.error:
            raise self.error
        self.calls.append(list(texts))
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in _tokens(text):
                vector[int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dimensions] += 1.0
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([v / norm for v in vector])
        return vectors


class FakeIndex:
    """Honours the workspace filter *as written in the request body*, like OpenSearch would.

    A body without the filter searches every workspace, so a service that forgets it fails the
    isolation tests instead of passing by accident.
    """

    def __init__(self) -> None:
        self.exists = True
        self.error: Exception | None = None
        self.created_with: dict | None = None
        self.chunks: dict[str, dict] = {}
        self.bodies: list[dict] = []
        self.fail_index = False

    def index_exists(self) -> bool:
        if self.error:
            raise self.error
        return self.exists

    def ensure_index(self, body: dict) -> bool:
        if self.exists and self.created_with is not None:
            return False
        self.exists, self.created_with = True, body
        return True

    def index_chunks(self, chunks: list[dict]) -> None:
        if self.fail_index:
            raise ConnectionError("bulk failed")
        for chunk in chunks:
            self.chunks[chunk["chunk_id"]] = dict(chunk)

    def search(self, body: dict) -> list[SearchHit]:
        if self.error:
            raise self.error
        self.bodies.append(body)
        query = body["query"]
        if "knn" in query:
            clause = query["knn"]["embedding"]
            workspace = (clause.get("filter") or {}).get("term", {}).get("workspace_id")
            scored = [
                (sum(a * b for a, b in zip(clause["vector"], c["embedding"], strict=True)), c)
                for c in self._in(workspace)
            ]
            scored = [(s, c) for s, c in scored if s > 0]
        else:
            filters = query["bool"].get("filter", [])
            workspace = next((f["term"]["workspace_id"] for f in filters if "term" in f), None)
            words = set(_tokens(query["bool"]["must"][0]["match"]["text"]["query"]))
            scored = [(float(len(words & set(_tokens(c["text"])))), c) for c in self._in(workspace)]
            scored = [(s, c) for s, c in scored if s > 0]
        scored.sort(key=lambda pair: (-pair[0], pair[1]["chunk_id"]))
        return [
            SearchHit(
                chunk_id=c["chunk_id"],
                score=s,
                source={k: v for k, v in c.items() if k != "embedding"},
            )
            for s, c in scored[: body["size"]]
        ]

    def _in(self, workspace: str | None) -> list[dict]:
        return [
            c for c in self.chunks.values() if workspace is None or c["workspace_id"] == workspace
        ]


class FakeAnswerer:
    """Records every call. By default it cites the first evidence item; tests set `draft` or `error`."""

    provider = "fake"
    model_id = "fake-answer-model"

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[dict]]] = []
        self.draft: AnswerDraft | None = None
        self.error: Exception | None = None

    def answer(self, question: str, evidence: list[dict]) -> AnswerResult:
        self.calls.append((question, [dict(e) for e in evidence]))
        if self.error:
            raise self.error
        draft = self.draft or AnswerDraft(
            answer=evidence[0]["quoted_span"],
            claims=[
                {"text": evidence[0]["quoted_span"], "evidence_ids": [evidence[0]["evidence_id"]]}
            ],
        )
        return AnswerResult(
            draft=draft, provider=self.provider, model_id=self.model_id, latency_ms=1
        )
