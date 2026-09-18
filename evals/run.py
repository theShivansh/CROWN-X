"""CROWN-X evaluation runner (docs/EVALUATION.md). Seeds the demo corpus, asks every golden question
through the public API contract, and writes exact metrics.

    # Offline: the real API handlers in-process, MockProvider, in-memory storage. No network, no AWS.
    cd services/api && uv run python ../../evals/run.py --offline

    # Live: any deployed stack (seeds fresh workspaces through the API first).
    cd services/api && uv run python ../../evals/run.py --api https://<api-id>.execute-api.ap-south-1.amazonaws.com

Writes evals/results/<UTC timestamp>-<mode>.json and prints the summary. Exit code 1 if the security
gate fails (any isolation, injection, zero-model-call, citation or evidence-integrity case). Live
Bedrock metrics are filled only when /health reports Bedrock for both answers and embeddings.
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
RESULTS = EVALS / "results"
sys.path[:0] = [str(EVALS), str(ROOT / "demo"), str(ROOT / "services" / "api" / "src")]

from metrics import summarize  # noqa: E402

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
    """The deployed handler code (`build_resolver`) over in-memory storage and MockProvider.

    Storage doubles come from services/api/tests/fakes.py: this is the evaluation harness, and the
    deployed code never imports them. Providers come from the real ProviderRouter, in `test` mode.
    """

    def __init__(self) -> None:
        sys.path.insert(0, str(ROOT / "services" / "api" / "tests"))
        from crownx.adapters.providers import ProviderRouter
        from crownx.app.api import build_resolver
        from crownx.app.ingestion import IngestionWorker
        from crownx.app.service import CrownService, Limits
        from crownx.config import Settings
        from fakes import FakeIndex, FakeObjects, FakeStore

        settings = Settings(
            environment="test",
            answer_provider="mock",
            embedding_provider="mock",
            aws_region="offline",
            documents_bucket="offline",
            table_name="offline",
            opensearch_endpoint="offline",
            ingest_function_name="offline",
            bedrock_embedding_model_id="amazon.titan-embed-text-v2:0",
        )
        providers = ProviderRouter.build(settings, session=None)
        self._objects = FakeObjects()
        store, index = FakeStore(), FakeIndex()
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
            providers=providers.describe(),
            limits=Limits(
                max_upload_bytes=settings.max_upload_bytes,
                max_documents_per_workspace=settings.max_documents_per_workspace,
                upload_url_expiry_seconds=settings.upload_url_expiry_seconds,
                retrieval_top_k=settings.retrieval_top_k,
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
    def __init__(self, api: str) -> None:
        self._api = api.rstrip("/")

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        import urllib.error
        import urllib.request

        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"{self._api}{path}",
            data=data,
            method=method,
            headers={"content-type": "application/json"} if data else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def put_object(self, upload: dict, filename: str, content: bytes) -> None:
        from seed import post_to_s3

        post_to_s3(upload, filename, content)

    def after_complete(self) -> None:
        pass


# ---------------------------------------------------------------- shared


def seed(client: Client, timeout_s: int) -> dict[str, dict]:
    """Workspace per corpus, documents uploaded in the SCENARIO.md §2 order, all settled."""
    from seed import WORKSPACE_A, WORKSPACE_B

    order = {"A": WORKSPACE_A, "B": WORKSPACE_B, "EMPTY": []}
    workspaces: dict[str, dict] = {}
    for name, filenames in order.items():
        status, body = client.call("POST", "/workspaces")
        assert status == 201, body
        ws = body["workspace"]["workspace_id"]
        folder = CORPUS[name]
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
    answer_ms = (time.perf_counter() - started) * 1000
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
    summary = summarize(cases, outcomes, providers)
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


def print_summary(report: dict) -> None:
    offline, live = report["offline"], report["live_bedrock"]
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
    print("\nLive Bedrock metrics (external gate)")
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CROWN-X golden set.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--offline", action="store_true", help="in-process, MockProvider")
    target.add_argument("--api", help="base URL of a deployed stack")
    parser.add_argument("--timeout", type=int, default=180, help="seconds to wait per document")
    parser.add_argument("--no-write", action="store_true", help="don't write a results file")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

    client: Any = InProcessClient() if args.offline else HttpClient(args.api)
    mode = "offline" if args.offline else "live"
    report = evaluate(client, mode, args.timeout)
    if not args.no_write:
        RESULTS.mkdir(parents=True, exist_ok=True)
        path = RESULTS / f"{report['run_at'].replace(':', '')}-{mode}.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    print_summary(report)
    sys.exit(0 if report["security_gate_passed"] else 1)


if __name__ == "__main__":
    main()
