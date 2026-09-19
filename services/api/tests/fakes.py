"""In-memory doubles of the ports in `crownx.adapters.ports`. They live only under tests/."""

from __future__ import annotations

import hashlib
import math
import re

from crownx.adapters.ports import AnswerResult, ObjectInfo, SearchHit
from crownx.domain.answering import AnswerDraft
from crownx.domain.claims import Claim
from crownx.domain.events import WorkflowEvent
from crownx.domain.models import Document, DocumentStatus, QueryRecord, Workspace


class FakeStore:
    def __init__(self) -> None:
        self.workspaces: dict[str, Workspace] = {}
        self.documents: dict[tuple[str, str], Document] = {}
        self.checksums: dict[tuple[str, str], str] = {}
        self.queries: dict[tuple[str, str], QueryRecord] = {}
        self.audit: list[tuple[str, dict]] = []
        self.events: dict[str, WorkflowEvent] = {}
        self.claims: dict[tuple[str, str], list[Claim]] = {}  # (workspace, document) -> claims
        self.event_error: Exception | None = None
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

    def count_usage(self, workspace_id: str, kind: str, window: str, expires_at: int) -> int:
        usage = self.__dict__.setdefault("usage", {})
        slot = (workspace_id, kind, window)
        usage[slot] = usage.get(slot, 0) + 1
        return usage[slot]

    def put_event(self, event: WorkflowEvent) -> None:
        if self.event_error:
            raise self.event_error
        self.events.setdefault(event.event_id, event)

    def list_events(self, workspace_id: str, limit: int = 2000) -> list[WorkflowEvent]:
        found = [e for e in self.events.values() if e.workspace_id == workspace_id]
        return sorted(found, key=lambda e: (e.occurred_at, e.event_id))[-limit:]

    def claim_event_id(self, workspace_id: str, event_id: str) -> bool:
        claimed = self.__dict__.setdefault("claimed_event_ids", set())
        if (workspace_id, event_id) in claimed:
            return False
        claimed.add((workspace_id, event_id))
        return True

    def get_workflow_states(self, workspace_id: str) -> dict[str, dict]:
        states = self.__dict__.setdefault("workflow_states", {})
        return {sid: dict(s) for (ws, sid), s in states.items() if ws == workspace_id}

    def put_workflow_state(self, workspace_id: str, suggestion_id: str, state: dict) -> None:
        self.__dict__.setdefault("workflow_states", {})[(workspace_id, suggestion_id)] = dict(state)

    def add_template(self, workspace_id: str, suggestion_id: str, template: dict) -> int:
        templates = self.__dict__.setdefault("templates", [])
        version = 1 + sum(
            1 for ws, t in templates if ws == workspace_id and t["suggestion_id"] == suggestion_id
        )
        templates.append((workspace_id, {**template, "version": version}))
        return version

    def list_templates(self, workspace_id: str) -> list[dict]:
        return [dict(t) for ws, t in self.__dict__.get("templates", []) if ws == workspace_id]

    def event_types(self, workspace_id: str) -> list[str]:
        return [e.event_type.value for e in self.list_events(workspace_id)]

    def replace_claims(self, workspace_id: str, document_id: str, claims: list[Claim]) -> None:
        self._check()
        self.claims[(workspace_id, document_id)] = list(claims)

    def list_claims(self, workspace_id: str) -> list[Claim]:
        self._check()
        return [c for (ws, _), found in self.claims.items() if ws == workspace_id for c in found]


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
        self.kinds: list[str] = []
        self.error: Exception | None = None

    def embed(self, texts: list[str], kind: str = "passage") -> list[list[float]]:
        if self.error:
            raise self.error
        self.calls.append(list(texts))
        self.kinds.append(kind)
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
            candidates = [c for c in self.chunks.values() if _matches(clause.get("filter"), c)]
            scored = [
                (sum(a * b for a, b in zip(clause["vector"], c["embedding"], strict=True)), c)
                for c in candidates
                if len(c["embedding"]) == len(clause["vector"])
            ]
            scored = [(s, c) for s, c in scored if s > 0]
        else:
            filters = {"bool": {"filter": query["bool"].get("filter", [])}}
            candidates = [c for c in self.chunks.values() if _matches(filters, c)]
            words = set(_tokens(query["bool"]["must"][0]["match"]["text"]["query"]))
            scored = [(float(len(words & set(_tokens(c["text"])))), c) for c in candidates]
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


def _matches(clause: dict | None, chunk: dict) -> bool:
    """`term` and `bool.filter` exactly as written; no clause means no filtering at all."""
    if not clause:
        return True
    if "term" in clause:
        [(field, value)] = clause["term"].items()
        return chunk.get(field) == value
    if "bool" in clause:
        return all(_matches(inner, chunk) for inner in clause["bool"].get("filter", []))
    raise AssertionError(f"FakeIndex doesn't understand {clause}")


class FakeAnswerer:
    """Records every call. By default it cites the first evidence item; tests set `draft` or `error`."""

    provider = "fake"
    model_id = "fake-answer-model"

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[dict]]] = []
        self.conflicts: list[list[dict]] = []
        self.draft: AnswerDraft | None = None
        self.error: Exception | None = None

    def answer(
        self, question: str, evidence: list[dict], conflicts: list[dict] | None = None
    ) -> AnswerResult:
        self.calls.append((question, [dict(e) for e in evidence]))
        self.conflicts.append(list(conflicts or []))
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
