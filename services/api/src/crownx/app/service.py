"""Workspace and document use cases, written against ports so tests run without AWS."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from crownx.adapters.ports import (
    Answerer,
    Embedder,
    IngestQueue,
    MetadataStore,
    ObjectStore,
    Reranker,
    SearchHit,
    SearchIndex,
)
from crownx.app.events import record_event
from crownx.domain.answering import FinalAnswer, finalize, insufficient
from crownx.domain.conflicts import ConflictGroup, audit_record, detect, group_view
from crownx.domain.errors import (
    AnswerUnavailable,
    InvalidRequest,
    LimitReached,
    NotFound,
    RetrievalUnavailable,
    TooLarge,
    UploadIncomplete,
)
from crownx.domain.events import EventType
from crownx.domain.fusion import near_duplicates, reciprocal_rank_fusion
from crownx.domain.ids import (
    is_document_id,
    is_query_id,
    is_workspace_id,
    new_document_id,
    new_query_id,
    new_workspace_id,
)
from crownx.domain.injection import instruction_like
from crownx.domain.models import Document, DocumentStatus, QueryRecord, Workspace, utc_now
from crownx.domain.retrieval import EmbeddingNamespace, lexical_query, semantic_query
from crownx.domain.timeline import KEYS as TIMELINE_KEYS
from crownx.domain.timeline import timeline
from crownx.domain.uploads import object_key, validate_upload
from crownx.domain.vocabulary import asks_about
from crownx.domain.workflow import DEFINITIONS, MinerConfig, WorkflowSuggestion, mine

log = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 500
RRF_K = 60


@dataclass(frozen=True)
class Limits:
    max_upload_bytes: int
    max_documents_per_workspace: int
    upload_url_expiry_seconds: int
    retrieval_top_k: int = 8
    # Fused-score floor below which a passage isn't evidence. 0 keeps everything; calibrated on the
    # golden set once live embeddings run (docs/EVALUATION.md).
    retrieval_score_floor: float = 0.0
    # Candidates each ranking contributes before fusion, dedup and the optional rerank (ADR-017).
    retrieval_candidates: int = 15
    # "hybrid" in every deployment; "bm25" and "dense" exist so the evaluation can compare them.
    retrieval_mode: str = "hybrid"
    duplicate_threshold: float = 0.9
    # How many fused candidates the cross-encoder re-scores; the rest keep their fused order after
    # them. Its cost grows linearly with this number (docs/BENCHMARKS.md).
    rerank_candidates: int = 8


@dataclass(frozen=True)
class QueryResult:
    query_id: str
    status: str  # "retrieved" or "insufficient_evidence" (SRS §3, stage 1)
    evidence: list[dict]
    timings_ms: dict[str, int] | None = None  # embed, search, rerank: for logs and the evaluation
    conflicts: list[dict] | None = None  # the conflict groups touching this evidence (M3)


@dataclass(frozen=True)
class AnswerOutcome:
    query_id: str
    final: FinalAnswer
    provider: str | None  # None when no model was called
    model_id: str | None  # the model that answered, which is the fallback model after a fallback
    attempts: tuple[dict, ...] = ()
    conflicts: tuple[dict, ...] = ()  # audit view: IDs, confidence, rule; no text


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
        embedder: Embedder,
        limits: Limits,
        namespace: EmbeddingNamespace,
        answerer: Answerer | None = None,
        providers: dict | None = None,
        reranker: Reranker | None = None,
        miner: MinerConfig | None = None,
    ) -> None:
        self._store = store
        self._objects = objects
        self._ingest = ingest
        self._index = index
        self._embedder = embedder
        self._limits = limits
        self._answerer = answerer
        self._namespace = namespace
        self._providers = providers or {}
        self._reranker = reranker
        self._miner = miner or MinerConfig()

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
        self._event(workspace_id, EventType.DOCUMENT_UPLOAD_REQUESTED, document_id=document_id)
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
            self._event(
                workspace_id,
                EventType.DOCUMENT_DUPLICATE,
                document_id=document_id,
                duplicate_of=owner,
            )
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
        self._event(
            workspace_id,
            EventType.DOCUMENT_UPLOADED,
            document_id=document_id,
            content_type=document.content_type,
            size_bytes=info.size_bytes,
        )
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

    # Retrieval ----------------------------------------------------------------------------------

    def query(self, workspace_id: str, question: str, request_id: str | None = None) -> QueryResult:
        """Stage 1 of a question (ADR-009): BM25 and k-NN, each filtered by workspace, fused by RRF."""
        self.require_workspace(workspace_id)
        question = question.strip()
        if not question or len(question) > MAX_QUESTION_CHARS:
            raise InvalidRequest(f"Ask a question between 1 and {MAX_QUESTION_CHARS} characters.")

        self._event(workspace_id, EventType.QUESTION_ASKED, question_chars=len(question))
        limits = self._limits
        mode = limits.retrieval_mode
        pool = max(limits.retrieval_candidates, limits.retrieval_top_k)
        timings: dict[str, int] = {}
        started = time.perf_counter()
        try:
            lexical: list[SearchHit] = []
            semantic: list[SearchHit] = []
            if mode in ("hybrid", "dense"):
                vector = self._embedder.embed([question], kind="query")[0]
                timings["embed"] = _ms_since(started)
            search_started = time.perf_counter()
            if mode in ("hybrid", "bm25"):
                lexical = self._index.search(
                    lexical_query(question, workspace_id, pool, self._namespace)
                )
            if mode in ("hybrid", "dense"):
                semantic = self._index.search(
                    semantic_query(vector, workspace_id, pool, self._namespace)
                )
            timings["search"] = _ms_since(search_started)
        except Exception as exc:
            log.exception("retrieval failed")
            raise RetrievalUnavailable(
                "Evidence couldn't be retrieved right now, so no answer was attempted. "
                "Retry in a moment."
            ) from exc

        hits: dict[str, SearchHit] = {hit.chunk_id: hit for hit in [*semantic, *lexical]}
        if any(not self._in_scope(hit.source, workspace_id) for hit in hits.values()):
            # The filters are inside both queries, so this can't happen; if it does, fail closed.
            raise RuntimeError("search returned a chunk from another workspace or namespace")

        rankings = [r for r in ([h.chunk_id for h in lexical], [h.chunk_id for h in semantic]) if r]
        candidates = [
            hit
            for hit in reciprocal_rank_fusion(rankings, k=RRF_K)
            if hit.score >= limits.retrieval_score_floor
        ]
        dropped = near_duplicates(
            [
                (
                    c.chunk_id,
                    hits[c.chunk_id].source["document_id"],
                    hits[c.chunk_id].source["text"],
                )
                for c in candidates
            ],
            limits.duplicate_threshold,
        )
        candidates = [c for c in candidates if c.chunk_id not in dropped][:pool]
        if self._reranker is not None and len(candidates) > 1:
            rerank_started = time.perf_counter()
            try:
                head = candidates[: limits.rerank_candidates]
                scores = self._reranker.scores(
                    question, [hits[c.chunk_id].source["text"] for c in head]
                )
                # Stable: equal rerank scores keep their fused order.
                order = sorted(range(len(head)), key=lambda i: (-scores[i], i))
                candidates = [head[i] for i in order] + candidates[len(head) :]
            except Exception:  # noqa: BLE001  # the fused order is still valid evidence
                log.exception("rerank failed; keeping the fused order")
            timings["rerank"] = _ms_since(rerank_started)
        fused = candidates[: limits.retrieval_top_k]
        filenames: dict[str, str | None] = {}
        for doc_id in {hits[f.chunk_id].source["document_id"] for f in fused}:
            doc = self._store.get_document(workspace_id, doc_id)
            filenames[doc_id] = doc.filename if doc else None
        evidence = []
        for rank, hit in enumerate(fused, start=1):
            source = hits[hit.chunk_id].source
            evidence.append(
                {
                    "evidence_id": f"ev_{rank}",
                    "chunk_id": hit.chunk_id,
                    "document_id": source["document_id"],
                    "filename": filenames.get(source["document_id"]),
                    "quoted_span": source["text"],
                    "page_or_section": source.get("page_or_section"),
                    "char_start": source["char_start"],
                    "char_end": source["char_end"],
                    "version_label": source.get("version_label"),
                    "source_timestamp": source.get("source_timestamp"),
                    "retrieval_rank": rank,
                    "retrieval_score": round(hit.score, 6),
                }
            )
        compare_started = time.perf_counter()
        conflicts = self._conflicts_touching(workspace_id, question, evidence)
        timings["compare"] = _ms_since(compare_started)
        record = QueryRecord(
            query_id=new_query_id(),
            workspace_id=workspace_id,
            question=question,
            status="retrieved" if evidence else "insufficient_evidence",
            evidence=evidence,
            conflicts=[group_view(g) for g in conflicts],
            created_at=utc_now(),
            request_id=request_id,
            retrieval_ms=round((time.perf_counter() - started) * 1000),
        )
        self._store.put_query(record)
        self._event(
            workspace_id,
            EventType.EVIDENCE_RETRIEVED,
            query_id=record.query_id,
            evidence_count=len(evidence),
            retrieval_ms=record.retrieval_ms,
        )
        return QueryResult(
            query_id=record.query_id,
            status=record.status,
            evidence=evidence,
            timings_ms=timings,
            conflicts=record.conflicts,
        )

    # Conflicts (M3, ADR-003, ADR-020) -----------------------------------------------------------

    def conflicts(self, workspace_id: str) -> list[dict]:
        """Every conflict in the workspace, derived from its claims now: never stale."""
        self.require_workspace(workspace_id)
        return [group_view(g) for g in detect(self._store.list_claims(workspace_id))]

    def timeline(self, workspace_id: str, subject: str, attribute: str) -> dict:
        """One fact's value history, ordered by the selection rule's own signals (FR-09)."""
        key = f"{subject}/{attribute}"
        if key not in TIMELINE_KEYS:
            raise InvalidRequest(
                "There is no timeline for that fact. Choose one of: "
                + ", ".join(sorted(TIMELINE_KEYS))
                + "."
            )
        self.require_workspace(workspace_id)
        return timeline(self._store.list_claims(workspace_id), key)

    def _conflicts_touching(
        self, workspace_id: str, question: str, evidence: list[dict]
    ) -> list[ConflictGroup]:
        """The groups where a conflicting claim's chunk was retrieved and the question names the
        fact (ADR-020). Both tests are code over IDs and the vocabulary, never the model."""
        if not evidence:
            return []
        retrieved = {e["chunk_id"] for e in evidence}
        return [
            group
            for group in detect(self._store.list_claims(workspace_id))
            if asks_about(group.key, question)
            and any(
                claim.source_chunk_id in retrieved
                for pair in group.pairs
                for claim in (pair.older, pair.newer)
            )
        ]

    def answer(
        self, workspace_id: str, query_id: str, request_id: str | None = None
    ) -> AnswerOutcome:
        """Stage 2 (ADR-009): one model call over exactly the stored evidence, or none at all."""
        self.require_workspace(workspace_id)
        record = self._store.get_query(workspace_id, query_id) if is_query_id(query_id) else None
        if record is None:
            raise NotFound("Question not found in this workspace. Ask it again.")

        audit = {
            "event_type": "answer",
            "request_id": request_id or "unknown",
            "query_id": query_id,
            "timestamp": utc_now(),
            "evidence_ids": [e["evidence_id"] for e in record.evidence],
            # Which deployment and providers were active (ADR-017, observability).
            "environment": self._providers.get("environment"),
            "answer_provider": self._providers.get("answer_provider"),
            "embedding_provider": self._providers.get("embedding_provider"),
            "embedding_model": self._providers.get("embedding_model"),
        }
        if not record.evidence:
            # The zero-model-call path (CLAUDE.md rule 1): nothing to ground an answer in.
            self._store.put_audit(workspace_id, {**audit, "outcome": "insufficient_evidence"})
            self._event(
                workspace_id, EventType.ANSWER_INSUFFICIENT, query_id=query_id, model_calls=0
            )
            return AnswerOutcome(query_id, insufficient(), provider=None, model_id=None)
        if self._answerer is None:
            self._event(workspace_id, EventType.ANSWER_UNAVAILABLE, query_id=query_id)
            raise AnswerUnavailable(
                "Answering isn't configured for this deployment, so no answer was written. "
                "The evidence panel still shows every retrieved passage."
            )

        answerer = self._answerer
        try:
            result = answerer.answer(record.question, record.evidence, record.conflicts)
        except Exception as error:
            self._store.put_audit(
                workspace_id,
                {
                    **audit,
                    "outcome": "error",
                    "error": type(error).__name__,
                    "provider": answerer.provider,
                    "model_id": answerer.model_id,
                    "answered_by_model": None,
                    "attempts": list(getattr(error, "attempts", ())),
                },
            )
            self._event(workspace_id, EventType.ANSWER_UNAVAILABLE, query_id=query_id)
            raise
        final = finalize(
            result.draft,
            {e["evidence_id"] for e in record.evidence},
            frozenset(
                e["evidence_id"] for e in record.evidence if instruction_like(e["quoted_span"])
            ),
            conflicted=bool(record.conflicts),
        )
        conflict_audit = tuple(item for group in record.conflicts for item in audit_record(group))
        if final.dropped:
            log.warning(
                "dropped %d claim(s) citing unknown or no evidence (request %s, query %s)",
                len(final.dropped),
                request_id,
                query_id,
            )
        self._store.put_audit(
            workspace_id,
            {
                **audit,
                "outcome": final.status,
                "provider": result.provider,
                "model_id": answerer.model_id,
                "answered_by_model": result.model_id,
                "attempts": list(result.attempts),
                "model_invocation_id": result.invocation_id,
                "latency_ms": result.latency_ms,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "claims_kept": len(final.claims),
                "claims_dropped": len(final.dropped),
                # Which conflicts the answer was written over: claim IDs, their extraction
                # confidence and the selection rule (ADR-020). No document text.
                "conflicts": list(conflict_audit),
            },
        )
        self._event(
            workspace_id,
            EventType.ANSWER_INSUFFICIENT
            if final.status == "insufficient_evidence"
            else EventType.ANSWER_GENERATED,
            query_id=query_id,
            status=final.status,
            answered_by_model=result.model_id,
        )
        return AnswerOutcome(
            query_id,
            final,
            provider=result.provider,
            model_id=result.model_id,
            attempts=result.attempts,
            conflicts=conflict_audit,
        )

    # Workflow Learning Lite (ADR-018) ------------------------------------------------------------

    def workflow_suggestions(self, workspace_id: str) -> tuple[list[WorkflowSuggestion], dict]:
        """Repeated sequences of this workspace's own actions. Suggestions only: nothing runs."""
        self.require_workspace(workspace_id)
        return mine(self._store.list_events(workspace_id), self._miner), DEFINITIONS

    def _event(self, workspace_id: str, event_type: EventType, **attributes: object) -> None:
        record_event(self._store, workspace_id, event_type, **attributes)

    def _in_scope(self, source: dict, workspace_id: str) -> bool:
        return source.get("workspace_id") == workspace_id and all(
            source.get(field) == value
            for field, value in self._namespace.fields().items()
            if field != "vector_dim"
        )

    def providers(self) -> dict:
        """Which environment and providers are active (ADR-016); shown by /health and the UI."""
        return dict(self._providers)

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


def _ms_since(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
