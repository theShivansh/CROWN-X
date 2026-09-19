"""CROWN-X evaluation runner (docs/EVALUATION.md). Seeds the demo corpus, asks every golden question
through the public API contract, and writes exact metrics.

    # Offline gate: the real API handlers in-process, in-memory storage, a local BM25Okapi + FAISS
    # index, and the real GroqAnswerer over the scripted MockGroqTransport. No network, no AWS.
    cd services/api && uv run python ../../evals/run.py --offline
    # ... with a real local embedding model (after `python scripts/fetch_models.py`):
    cd services/api && uv run python ../../evals/run.py --offline --embedding multilingual-e5-small-int8

    # Retrieval benchmark: BM25 vs dense vs hybrid vs hybrid + rerank, for each local model.
    cd services/api && uv run python ../../evals/run.py --compare

    # Retrieval benchmark v2 (60 passages, 30 queries, passage-level relevance). /query only, so
    # neither run touches the answer model or Groq's quota.
    cd services/api && uv run python ../../evals/run.py --compare --dataset retrieval-v2
    cd services/api && uv run python ../../evals/run.py --api <ApiUrl> --retrieval-only --dataset retrieval-v2

    # Live gate: any deployed stack (seeds fresh workspaces through the API first), paced for Groq.
    cd services/api && uv run python ../../evals/run.py --api https://<api-id>.execute-api.ap-south-1.amazonaws.com --pace 2.5

Writes evals/results/<UTC timestamp>-<mode>.json and prints the summary. Exit code 1 if the security
gate fails (any isolation, injection, zero-model-call, citation or evidence-integrity case). Live
metrics are filled only for a deployed run whose /health reports real providers (never the mock).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
DATASET = EVALS / "golden" / "v1.jsonl"
# Same answers as v1 cases, asked in other words or in Hinglish: vocabulary mismatch, for --compare.
PARAPHRASE = EVALS / "golden" / "paraphrase-v1.jsonl"
# Retrieval benchmark v2: 60 passages (12 documents x 5 sections) and 30 passage-labelled queries.
RETRIEVAL_V2 = EVALS / "golden" / "retrieval-v2.jsonl"
RETRIEVAL_V2_CORPUS = EVALS / "corpus" / "retrieval-v2"
RETRIEVAL_V2_PASSAGES = 60
RESULTS = EVALS / "results"
MODELS = ROOT / "services" / "api" / ".models"
sys.path[:0] = [str(EVALS), str(ROOT / "demo"), str(ROOT / "services" / "api" / "src")]

from metrics import passage_key, passage_metrics, retrieval_metrics, summarize  # noqa: E402

CORPUS = {
    "A": ROOT / "demo" / "documents" / "workspace-a",
    "B": ROOT / "demo" / "documents" / "workspace-b",
    "EMPTY": ROOT / "demo" / "documents",  # nothing is uploaded: the zero-model-call cases
}


class Client(Protocol):
    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]: ...

    def put_object(self, upload: dict, filename: str, content: bytes) -> None: ...

    def after_complete(self) -> None: ...


# ---------------------------------------------------------------- offline: in-process, MockProvider


class InProcessClient:
    """The deployed handler code (`build_resolver`) over in-memory storage and a local index.

    Storage doubles come from services/api/tests/fakes.py: this is the evaluation harness, and the
    deployed code never imports them. Providers come from the real ProviderRouter, in `test` mode:
    answers from the production `GroqAnswerer` over the scripted `MockGroqTransport` (no network, no
    rate limit), embeddings from the mock or from a downloaded local ONNX model.
    """

    def __init__(
        self,
        embedding: str = "mock",
        retrieval_mode: str = "hybrid",
        reranker: bool = False,
    ) -> None:
        sys.path.insert(0, str(ROOT / "services" / "api" / "tests"))
        from crownx.adapters.onnx_models import sha256_of
        from crownx.adapters.providers import ProviderRouter
        from crownx.app.api import build_resolver
        from crownx.app.ingestion import IngestionWorker
        from crownx.app.service import CrownService, Limits
        from crownx.config import Settings
        from fakes import FakeObjects, FakeStore
        from local_index import LocalHybridIndex

        def local_model(name: str) -> dict:
            directory = MODELS / name
            if not (directory / "model.onnx").exists():
                raise SystemExit(f"{name} isn't downloaded: run python scripts/fetch_models.py")
            return {"uri": str(directory), "sha256": sha256_of(directory / "model.onnx")}

        options: dict = {}
        if embedding != "mock":
            model = local_model(embedding)
            options |= {
                "embedding_provider": "onnx",
                "onnx_model_name": embedding,
                "onnx_model_uri": model["uri"],
                "onnx_model_sha256": model["sha256"],
            }
        if reranker:
            model = local_model(RERANKER)
            options |= {
                "reranker_enabled": True,
                "reranker_model_name": RERANKER,
                "reranker_model_uri": model["uri"],
                "reranker_model_sha256": model["sha256"],
            }
        settings = Settings(
            **{
                "environment": "test",
                "answer_provider": "groq",
                "groq_transport": "mock",
                "groq_model_id": "openai/gpt-oss-120b",
                "groq_fallback_model_id": "openai/gpt-oss-20b",
                "embedding_provider": "mock",
                "aws_region": "offline",
                "documents_bucket": "offline",
                "table_name": "offline",
                "opensearch_endpoint": "offline",
                "ingest_function_name": "offline",
                **options,
            }
        )
        providers = ProviderRouter.build(settings, session=None)
        self.providers = providers.describe() | {
            "answer_transport": "mock (scripted, no network)",
            "index": "local BM25Okapi + FAISS IndexFlatIP",
            "retrieval_mode": retrieval_mode,
        }
        self._objects = FakeObjects()
        store, index = FakeStore(), LocalHybridIndex()
        self._queued: list[tuple[str, str]] = []
        worker = IngestionWorker(
            store, self._objects, providers.embedder, index, providers.namespace
        )
        self._worker = worker

        client = self

        class InlineIngest:
            def enqueue(self, workspace_id: str, document_id: str) -> None:
                client._queued.append((workspace_id, document_id))

        service = CrownService(
            store=store,
            objects=self._objects,
            ingest=InlineIngest(),
            index=index,
            embedder=providers.embedder,
            namespace=providers.namespace,
            answerer=providers.answerer,
            reranker=providers.reranker,
            providers=self.providers,
            limits=Limits(
                max_upload_bytes=settings.max_upload_bytes,
                max_documents_per_workspace=settings.max_documents_per_workspace,
                upload_url_expiry_seconds=settings.upload_url_expiry_seconds,
                retrieval_top_k=settings.retrieval_top_k,
                retrieval_mode=retrieval_mode,
            ),
        )
        self._resolver = build_resolver(lambda: service)
        self._requests = 0

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        self._requests += 1
        event = {
            "version": "2.0",
            "routeKey": "$default",
            "rawPath": path,
            "rawQueryString": "",
            "headers": {"content-type": "application/json"},
            "requestContext": {
                "http": {"method": method, "path": path},
                "requestId": f"eval{self._requests:05d}",
                "stage": "$default",
            },
            "body": None if body is None else json.dumps(body),
            "isBase64Encoded": False,
        }
        response = self._resolver.resolve(event, object())
        return response["statusCode"], json.loads(response["body"])

    def put_object(self, upload: dict, filename: str, content: bytes) -> None:
        self._objects.objects[upload["fields"]["key"]] = content

    def after_complete(self) -> None:
        while self._queued:  # the async ingestion Lambda, run inline
            self._worker.ingest(*self._queued.pop(0))


# ---------------------------------------------------------------- live: any deployed API


class HttpClient:
    """A deployed stack. `pace_s` spaces out answer calls for Groq's free-tier rate limit; a 503
    `answer_unavailable` (rate limited even after the fallback) is retried after a pause."""

    def __init__(self, api: str, pace_s: float = 0.0) -> None:
        self._api = api.rstrip("/")
        self._pace_s = pace_s
        self._last_answer = 0.0

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        if not path.endswith("/answer"):
            return self._call(method, path, body)
        for attempt in range(3):
            wait = self._last_answer + self._pace_s - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_answer = time.monotonic()
            started = time.perf_counter()
            status, reply = self._call(method, path, body)
            # Server-side time only: the pacing sleep above is the client's choice, not latency.
            reply["_client_ms"] = (time.perf_counter() - started) * 1000
            code = (reply.get("error") or {}).get("code")
            if status != 503 or code != "answer_unavailable" or attempt == 2:
                return status, reply
            time.sleep(20 * (attempt + 1))  # the per-minute window resets
        raise AssertionError("unreachable")

    def _call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        import urllib.error
        import urllib.request

        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"{self._api}{path}",
            data=data,
            method=method,
            headers={"content-type": "application/json"} if data else {},
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=35) as response:
                    return response.status, json.loads(response.read())
            except urllib.error.HTTPError as error:
                return error.code, json.loads(error.read() or b"{}")
            except (urllib.error.URLError, TimeoutError) as error:
                # A dropped connection on this machine's side isn't an API result; retry it. Both
                # calls are safe to repeat: a query writes a new snapshot, an answer a new audit.
                if attempt == 2:
                    raise
                print(f"network error on {path} ({error}); retrying", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        raise AssertionError("unreachable")

    def put_object(self, upload: dict, filename: str, content: bytes) -> None:
        from seed import post_to_s3

        post_to_s3(upload, filename, content)

    def after_complete(self) -> None:
        pass


# ---------------------------------------------------------------- shared


def seed(
    client: Client, timeout_s: int, corpus: dict[str, tuple[Path, list[str]]] | None = None
) -> dict[str, dict]:
    """Workspace per corpus, all documents settled. By default the demo corpus, uploaded in the
    SCENARIO.md §2 order; `corpus` maps a workspace name to its folder and upload order."""
    from seed import WORKSPACE_A, WORKSPACE_B

    if corpus is None:
        corpus = {
            "A": (CORPUS["A"], WORKSPACE_A),
            "B": (CORPUS["B"], WORKSPACE_B),
            "EMPTY": (CORPUS["EMPTY"], []),
        }
    workspaces: dict[str, dict] = {}
    for name, (folder, filenames) in corpus.items():
        status, body = client.call("POST", "/workspaces")
        assert status == 201, body
        ws = body["workspace"]["workspace_id"]
        for filename in filenames:
            content = (folder / filename).read_bytes()
            status, ticket = client.call(
                "POST",
                f"/workspaces/{ws}/documents/upload-url",
                {"filename": filename, "size_bytes": len(content)},
            )
            assert status == 201, ticket
            client.put_object(ticket["upload"], filename, content)
            status, body = client.call(
                "POST", f"/workspaces/{ws}/documents/{ticket['document']['document_id']}/complete"
            )
            assert status == 200, body
            client.after_complete()
            _wait(client, ws, timeout_s)
        documents = _wait(client, ws, timeout_s)
        not_ready = [d["filename"] for d in documents if d["status"] != "ready"]
        if not_ready:
            raise SystemExit(f"workspace {name}: not ready: {not_ready}; see its documents' errors")
        workspaces[name] = {
            "workspace_id": ws,
            "documents": {d["document_id"]: d["filename"] for d in documents},
            "chunks": sum(d.get("chunk_count") or 0 for d in documents),
        }
    return workspaces


def _wait(client: Client, ws: str, timeout_s: int) -> list[dict]:
    deadline = time.monotonic() + timeout_s
    while True:
        _, body = client.call("GET", f"/workspaces/{ws}/documents")
        documents = body["documents"]
        if all(d["status"] in {"ready", "failed", "duplicate"} for d in documents):
            return documents
        if time.monotonic() > deadline:
            return documents
        time.sleep(1)


def run_case(client: Client, case: dict, workspace: dict) -> dict:
    ws = workspace["workspace_id"]
    started = time.perf_counter()
    status, query = client.call("POST", f"/workspaces/{ws}/query", {"question": case["question"]})
    query_ms = (time.perf_counter() - started) * 1000
    if status != 200:
        return {"error": f"query HTTP {status}: {query.get('error', {}).get('code')}"}
    started = time.perf_counter()
    status, answer = client.call("POST", f"/workspaces/{ws}/queries/{query['query_id']}/answer")
    answer_ms = answer.pop("_client_ms", None) or (time.perf_counter() - started) * 1000
    if status != 200:
        return {"error": f"answer HTTP {status}: {answer.get('error', {}).get('code')}"}
    return {
        "query_id": query["query_id"],
        "request_ids": [query["request_id"], answer["request_id"]],
        "status": answer["status"],
        "answer": answer["answer"],
        "claims": answer["claims"],
        "answer_provider": answer["answer_provider"],
        "model_id": answer["model_id"],
        "answered_by_model": answer.get("answered_by_model"),
        "attempts": answer.get("attempts") or [],
        "evidence": [
            {
                k: e.get(k)
                for k in ("evidence_id", "chunk_id", "document_id", "filename", "quoted_span")
            }
            for e in query["evidence"]
        ],
        "workspace_documents": list(workspace["documents"]),
        "timings_ms": {"query": round(query_ms, 1), "answer": round(answer_ms, 1)},
    }


def load_cases(path: Path = DATASET) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def evaluate(client: Client, mode: str, timeout_s: int = 180) -> dict:
    _, health = client.call("GET", "/health")
    providers = health.get("providers") or {}
    cases = load_cases()
    workspaces = seed(client, timeout_s)
    outcomes = {c["id"]: run_case(client, c, workspaces[c["workspace"]]) for c in cases}
    summary = summarize(cases, outcomes, providers, live=mode == "live")
    return {
        "dataset": DATASET.name.removesuffix(".jsonl"),
        "mode": mode,
        "run_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _commit(),
        "workspaces": {k: v["workspace_id"] for k, v in workspaces.items()},
        **summary,
        "outcomes": outcomes,
    }


def _commit() -> str:
    import subprocess

    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                cwd=ROOT,
                check=False,
            ).stdout.strip()
            or "unknown"
        )
    except OSError:
        return "unknown"


RERANKER = "ms-marco-MiniLM-L-6-v2-int8"
EMBEDDERS = ["multilingual-e5-small-int8", "bge-small-en-v1.5-int8"]


def retrieval_only(client: Client, cases: list[dict], workspaces: dict) -> dict[str, dict]:
    """Stage 1 only: the evidence each question retrieves, and how long retrieval took."""
    outcomes = {}
    for case in cases:
        ws = workspaces[case["workspace"]]["workspace_id"]
        started = time.perf_counter()
        status, query = client.call(
            "POST", f"/workspaces/{ws}/query", {"question": case["question"]}
        )
        elapsed = (time.perf_counter() - started) * 1000
        outcomes[case["id"]] = (
            {"error": f"query HTTP {status}"}
            if status != 200
            else {
                "evidence": [
                    {"filename": e.get("filename"), "page_or_section": e.get("page_or_section")}
                    for e in query["evidence"]
                ],
                "timings_ms": {"query": round(elapsed, 1)},
            }
        )
    return outcomes


def compare(
    embedders: list[str], timeout_s: int = 180, repeats: int = 3, dataset: Path = DATASET
) -> dict:
    """BM25 vs dense vs hybrid vs hybrid + rerank on the M2 answerable cases, in process, with the
    real local models. Each configuration runs `repeats` times on a fresh index: document IDs are
    random, so exact score ties can break differently; means are reported with the MRR range."""
    cases = [c for c in load_cases(dataset) if c["milestone"] == "M2" and c.get("expected_files")]
    configs = [("bm25", "mock", "bm25", False)]
    for name in embedders:
        configs += [
            ("dense", name, "dense", False),
            ("hybrid", name, "hybrid", False),
            ("hybrid + rerank", name, "hybrid", True),
        ]
    rows = []
    for label, embedding, retrieval_mode, rerank in configs:
        runs = []
        for _ in range(repeats):
            client = InProcessClient(embedding, retrieval_mode, rerank)
            workspaces = seed(client, timeout_s)
            retrieval_only(client, cases[:3], workspaces)  # warm the models before timing
            runs.append(retrieval_metrics(cases, retrieval_only(client, cases, workspaces)))
        mean = {
            key: round(sum(r[key] for r in runs) / len(runs), 4)
            for key in runs[0]
            if all(isinstance(r[key], int | float) for r in runs)
        }
        rows.append(
            {
                "system": label,
                "embedding_model": None if retrieval_mode == "bm25" else embedding,
                "reranker": RERANKER if rerank else None,
                **mean,
                "mrr_range": [min(r["mrr"] for r in runs), max(r["mrr"] for r in runs)],
                "repeats": repeats,
            }
        )
    return {
        "dataset": dataset.name.removesuffix(".jsonl"),
        "mode": "compare",
        "run_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _commit(),
        "cases": len(cases),
        "index": "local BM25Okapi + FAISS IndexFlatIP (in process)",
        "rows": rows,
    }


def seed_retrieval_v2(client: Client, timeout_s: int) -> dict[str, dict]:
    """One workspace holding the v2 corpus, which every v2 case asks. Refuses to measure unless the
    corpus indexed as exactly 60 passages, so a chunker change can't silently change the benchmark."""
    filenames = sorted(p.name for p in RETRIEVAL_V2_CORPUS.glob("*.md"))
    workspaces = seed(client, timeout_s, {"R": (RETRIEVAL_V2_CORPUS, filenames)})
    if workspaces["R"]["chunks"] != RETRIEVAL_V2_PASSAGES:
        raise SystemExit(
            f"retrieval v2 corpus indexed as {workspaces['R']['chunks']} passages, "
            f"expected {RETRIEVAL_V2_PASSAGES}"
        )
    return workspaces


def measure_v2(client: Client, cases: list[dict], workspaces: dict, repeats: int) -> dict:
    """Warm up, then ask the 30 queries `repeats` times. Quality is the mean over the repeats (the
    MRR range shows any tie-breaking spread); latency percentiles pool every repeat's timings."""
    retrieval_only(client, cases[:3], workspaces)  # load the models / warm the Lambda first
    runs = [retrieval_only(client, cases, workspaces) for _ in range(repeats)]
    pooled_cases = [c | {"id": f"{c['id']}@{n}"} for n in range(repeats) for c in cases]
    pooled = {f"{cid}@{n}": outcome for n, run in enumerate(runs) for cid, outcome in run.items()}
    per_run = [passage_metrics(cases, run) for run in runs]
    return passage_metrics(pooled_cases, pooled) | {
        "cases": len(cases),
        "mrr_range": [min(r["mrr"] for r in per_run), max(r["mrr"] for r in per_run)],
        "repeats": repeats,
        # The first run's ranked passages per case, so any miss can be read and checked by hand.
        "first_run": {
            cid: [passage_key(e) for e in outcome.get("evidence") or []]
            for cid, outcome in runs[0].items()
        },
    }


def benchmark_v2(embedders: list[str], timeout_s: int = 180, repeats: int = 3) -> dict:
    """Retrieval benchmark v2 in process with the real local models: every system on the
    60-passage corpus, each on a fresh index."""
    cases = load_cases(RETRIEVAL_V2)
    configs = [("bm25", "mock", "bm25", False)]
    for name in embedders:
        configs += [
            ("dense", name, "dense", False),
            ("hybrid", name, "hybrid", False),
            ("hybrid + rerank", name, "hybrid", True),
        ]
    rows = []
    for label, embedding, retrieval_mode, rerank in configs:
        client = InProcessClient(embedding, retrieval_mode, rerank)
        workspaces = {"R": seed_retrieval_v2(client, timeout_s)["R"]}
        rows.append(
            {
                "system": label,
                "embedding_model": None if retrieval_mode == "bm25" else embedding,
                "reranker": RERANKER if rerank else None,
                **measure_v2(client, cases, workspaces, repeats),
            }
        )
    return {
        "dataset": RETRIEVAL_V2.name.removesuffix(".jsonl"),
        "mode": "compare",
        "run_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _commit(),
        "cases": len(cases),
        "passages": RETRIEVAL_V2_PASSAGES,
        "index": "local BM25Okapi + FAISS IndexFlatIP (in process)",
        "rows": rows,
    }


def live_retrieval_v2(client: Client, timeout_s: int = 180, repeats: int = 3) -> dict:
    """Benchmark v2 on a deployed stack as its /health describes it. Latency is measured by this
    client, so it includes the network round trip to ap-south-1."""
    _, health = client.call("GET", "/health")
    cases = load_cases(RETRIEVAL_V2)
    workspaces = {"R": seed_retrieval_v2(client, timeout_s)["R"]}
    return {
        "dataset": RETRIEVAL_V2.name.removesuffix(".jsonl"),
        "mode": "live-retrieval",
        "run_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _commit(),
        "providers": health.get("providers") or {},
        "workspace": workspaces["R"]["workspace_id"],
        "passages": RETRIEVAL_V2_PASSAGES,
        **measure_v2(client, cases, workspaces, repeats),
    }


def print_v2(report: dict) -> None:
    rows = report.get("rows") or [
        {"system": "deployed", "embedding_model": report["providers"].get("embedding_model")}
        | report
    ]
    print(
        f"CROWN-X retrieval benchmark v2 · {report['passages']} passages · {rows[0]['cases']} "
        f"queries · {report['mode']} · commit {report['commit']}"
    )
    print("| System | Embedding model | Recall@5 | Recall@8 | MRR (range) | p50 ms | p95 ms |")
    print("|" + "---|" * 7)
    for r in rows:
        low, high = r["mrr_range"]
        print(
            f"| {r['system']} | {r['embedding_model'] or 'none'} | {r['recall_at_5']} | "
            f"{r['recall_at_8']} | {r['mrr']:.3f} ({low:.3f}-{high:.3f}) | "
            f"{r['p50_query_ms']:.0f} | {r['p95_query_ms']:.0f} |"
        )
    print("\nBy category (Recall@5 / Recall@8 / MRR):")
    for r in rows:
        cells = [
            f"{name} {m['recall_at_5']}/{m['recall_at_8']}/{m['mrr']}"
            for name, m in r["by_category"].items()
        ]
        print(f"  {r['system']} {r['embedding_model'] or ''}: " + " · ".join(cells))


def live_retrieval(client: Client, timeout_s: int = 180) -> dict:
    """Stage-1 quality and latency on a deployed stack, as its /health describes it."""
    _, health = client.call("GET", "/health")
    workspaces = seed(client, timeout_s)
    datasets = {}
    for name, path in (("v1", DATASET), ("paraphrase", PARAPHRASE)):
        cases = [c for c in load_cases(path) if c["milestone"] == "M2" and c.get("expected_files")]
        retrieval_only(client, cases[:3], workspaces)  # warm the Lambda and the models
        datasets[name] = retrieval_metrics(cases, retrieval_only(client, cases, workspaces))
    return {
        "mode": "live-retrieval",
        "run_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _commit(),
        "providers": health.get("providers") or {},
        "datasets": datasets,
    }


def print_compare(report: dict) -> None:
    print(
        f"CROWN-X retrieval comparison · dataset {report['dataset']} · {report['cases']} M2 "
        f"answerable cases · commit {report['commit']}"
    )
    print(
        "| System | Embedding model | Hit@5 | Hit@8 | Recall@5 | Recall@8 | MRR (mean) "
        "| MRR range | p50 ms | p95 ms |"
    )
    print("|" + "---|" * 10)
    for r in report["rows"]:
        low, high = r["mrr_range"]
        print(
            f"| {r['system']} | {r['embedding_model'] or 'none'} | {r['hit_rate_at_5']} | "
            f"{r['hit_rate_at_8']} | {r['recall_at_5']} | {r['recall_at_8']} | {r['mrr']:.3f} | "
            f"{low:.3f}-{high:.3f} | {r['p50_query_ms']:.0f} | {r['p95_query_ms']:.0f} |"
        )


def print_summary(report: dict) -> None:
    offline, live = report["offline"], report["live"]
    print(
        f"CROWN-X eval · dataset {report['dataset']} · {report['mode']} · commit {report['commit']}"
    )
    print(f"providers: {json.dumps(report['providers'])}")
    print("\nM2 offline gate (deterministic; provider-independent properties)")
    for key in (
        "m2_cases",
        "m2_errors",
        "m2_case_pass_rate",
        "citation_validity",
        "evidence_id_integrity",
        "workspace_isolation_pass_rate",
        "injection_pass_rate",
        "zero_model_call_pass_rate",
        "insufficient_evidence_correctness",
        "status_accuracy",
        "answer_value_match",
    ):
        print(f"  {key:36} {offline[key]}")
    retrieval = offline["retrieval"]
    print(f"  retrieval ({retrieval['label']}, semantic={retrieval['semantic']})")
    print(f"    hit_rate_at_8                      {retrieval['hit_rate_at_8']}")
    print(f"    mrr                                {retrieval['mrr']}")
    print("\nLive metrics (live gate: deployed stack, real providers)")
    for key, value in live.items():
        print(f"  {key:36} {value}")
    m3 = report["m3_expected_fail"]
    print(f"\nM3 cases: {m3['cases']} ({m3['note']})")
    print(f"\nsecurity gate passed: {report['security_gate_passed']}")
    worst = report["m2_failures"][:3]
    if worst:
        print("worst M2 failures:")
        for failure in worst:
            flags = [
                k
                for k in ("status_ok", "values_ok", "security_ok", "citations_valid")
                if failure.get(k) is False
            ]
            print(f"  {failure['id']} ({failure['category']}): {failure.get('error') or flags}")


def _write(report: dict, mode: str) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{report['run_at'].replace(':', '')}-{mode}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CROWN-X golden set.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--offline", action="store_true", help="in-process, scripted Groq")
    target.add_argument("--compare", action="store_true", help="retrieval benchmark, in-process")
    target.add_argument("--api", help="base URL of a deployed stack")
    parser.add_argument(
        "--embedding",
        default="mock",
        choices=["mock", *EMBEDDERS],
        help="offline only: the embedding model (a local ONNX model must be downloaded first)",
    )
    parser.add_argument("--rerank", action="store_true", help="offline only: enable the reranker")
    parser.add_argument(
        "--dataset",
        choices=["v1", "paraphrase", "retrieval-v2"],
        default="v1",
        help="compare and --retrieval-only: the golden set, its paraphrase and Hinglish variant, "
        "or retrieval benchmark v2",
    )
    parser.add_argument(
        "--pace", type=float, default=0.0, help="live only: seconds between answers"
    )
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="live only: stage 1 on v1 and the paraphrase set, no answer calls (no Groq quota)",
    )
    parser.add_argument("--timeout", type=int, default=180, help="seconds to wait per document")
    parser.add_argument("--no-write", action="store_true", help="don't write a results file")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

    if args.dataset == "retrieval-v2" and (args.compare or args.retrieval_only):
        report = (
            benchmark_v2(EMBEDDERS, args.timeout)
            if args.compare
            else live_retrieval_v2(HttpClient(args.api), args.timeout)
        )
        if not args.no_write:
            _write(report, "compare-retrieval-v2" if args.compare else "live-retrieval-v2")
        print_v2(report)
        return
    if args.compare:
        report = compare(
            EMBEDDERS, args.timeout, dataset=PARAPHRASE if args.dataset == "paraphrase" else DATASET
        )
        if not args.no_write:
            _write(report, f"compare-{args.dataset}")
        print_compare(report)
        return
    if args.api and args.retrieval_only:
        report = live_retrieval(HttpClient(args.api), args.timeout)
        if not args.no_write:
            _write(report, "live-retrieval")
        for name, row in report["datasets"].items():
            print(name, json.dumps(row))
        return
    client: Any = (
        InProcessClient(args.embedding, reranker=args.rerank)
        if args.offline
        else HttpClient(args.api, args.pace)
    )
    mode = "offline" if args.offline else "live"
    report = evaluate(client, mode, args.timeout)
    if not args.no_write:
        _write(report, mode)
    print_summary(report)
    sys.exit(0 if report["security_gate_passed"] else 1)


if __name__ == "__main__":
    main()
