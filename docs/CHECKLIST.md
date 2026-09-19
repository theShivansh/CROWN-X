# CROWN-X gate checklists

Each item is PASS, FAIL or NOT TESTED, with the evidence that was observed. A gate is GREEN only when
every item passes. Update this file whenever a gate is re-run.

## M2 Offline Gate: GREEN (2026-09-18 17:05 IST, commit `81f4630`)

Checked in one run on Windows 11 with uv-managed Python 3.12 and Node 22. The same checks run in CI on
every push (`.github/workflows/ci.yml`).

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | Backend tests | PASS | `cd services/api && uv run pytest -q`: 187 passed; `uv run ruff check src tests`: clean; `uv lock --check`: ok |
| 2 | Frontend checks | PASS | `cd apps/web`: `pnpm lint` clean, `pnpm typecheck` clean, `pnpm test` 11 passed, `pnpm build` compiled (static export `/` and `/app`) |
| 3 | PDF extraction, chunking, metadata | PASS | `test_ingestion.py` (page-by-page chunks, empty-text PDF fails with the SRS reason and indexes nothing, corrupt PDF fails, demo PDF single-spaced); `test_metadata.py` (every demo document's version and date, D6 null, ambiguous dates null) |
| 4 | Stored evidence snapshot | PASS | `test_answer_api.py`: the query record equals the returned evidence; `/answer` makes no search or embedding call even after the index is cleared |
| 5 | Citation validation | PASS | `test_answering.py` and `test_answer_api.py`: invented, partly invented and uncited claims dropped (`partial`); only invented leaves `insufficient_evidence`; the answer text is rebuilt from kept claims. Offline eval citation validity 1.0 |
| 6 | Prompt-injection handling | PASS | `test_answering.py`: a document can't close or forge an `<evidence>` block, and the injection line stays quoted data; `test_answer_providers.py`: evidence only in the user turn, forced `submit_answer` tool, extra fields rejected; the mock never repeats an instruction as a claim. Offline eval injection pass rate 1.0 (3 cases) |
| 7 | Cross-workspace isolation | PASS | `test_query_api.py` and `test_answer_api.py` (another workspace's facts never retrieved; a foreign `query_id` is 404, also observed live); `test_providers.py` (another embedding namespace never answers). Offline eval isolation 1.0 (7 cases) |
| 8 | Zero-model-call path | PASS | `test_answer_api.py`: no evidence means zero answerer calls and `answer_provider: null`; offline eval zero-model-call cases 1.0 (2 cases, empty workspace) |
| 9 | Provider abstraction | PASS | `test_providers.py`: production refuses mock and Groq, offline-demo is mock only, the router builds each provider from configuration, the whole pipeline runs on the mock with no code change. Live `/health` after redeploy: `environment: production`, `embedding_provider: bedrock`, `answer_provider: none` (no model configured) |
| 10 | Evaluation runner | PASS | `evals/run.py --offline`: 47 cases (40 M2, 7 M3 excluded), 0 errors, security gate passed; `test_evals.py` covers the metric functions and runs the offline evaluation end to end. Baseline in `docs/BENCHMARKS.md` |
| 11 | ADR | PASS | ADR-016 (architecture lock) recorded; ADR-013 kept proposed |
| 12 | PROGRESS and HANDOFF | PASS | `docs/PROGRESS.md` M2 row, next-session line, verification log; `docs/HANDOFF.md` |
| 13 | Git checkpoint | PASS | slices committed by path and pushed: `ad1a018` (A), `06d8b31` (B), `3226596` (C), `6ac4715` (D), `beab017` (E), `551708a` and `81f4630` (F), redeploy recorded after G |
| 14 | Redeploy (slice G) | PASS | `sam build` + `sam deploy`: UPDATE_COMPLETE; `ensure_index` added the namespace fields to the live mapping; `/health` 200 with every dependency `ok` |

### Re-run after ADR-017 and ADR-018: GREEN (2026-09-18 23:45 IST, working tree after `fbe3dea`)
Items 1 to 14 were re-checked where the code changed. Items 15 to 21 are new. No test, eval or check
touched the network: an autouse socket guard fails any outbound connection, and `GROQ_API_KEY` was
unset.

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | Backend tests | PASS | `uv run pytest -q`: 254 passed; `ruff check src tests`: clean; `uv lock --check`: ok; `requirements.txt` re-exported |
| 2 | Frontend checks | PASS | `pnpm lint`, `pnpm typecheck` clean; `pnpm test` 12 passed; `pnpm build` compiled |
| 5 | Citation validation | PASS | unchanged `finalize()`; `test_groq_reliability.py`: an invented ID from the Groq path is dropped (`partial`) |
| 6 | Prompt-injection handling | PASS | Groq path sends the same prompt and forced tool; offline eval injection 1.0 through `GroqAnswerer` |
| 7 | Cross-workspace isolation | PASS | offline eval isolation 1.0 on the local BM25 + FAISS index, which honours filters only as written |
| 9 | Provider abstraction | PASS | `test_providers.py`: production allows groq/onnx/bedrock, refuses the mock and the scripted transport; the Groq key comes from SSM once and is never described |
| 10 | Evaluation runner | PASS | `evals/run.py --offline`: security gate passed with mock and with e5-small embeddings (`evals/results/2026-09-18T1801*-offline.json`) |
| 15 | Groq reliability layer (deterministic MockGroq transport) | PASS | `test_groq_reliability.py`: ok, timeout retry, two timeouts then fallback, short Retry-After wait, long Retry-After straight to fallback, 500/malformed/no-tool fallback, both failing is 503 with every attempt, the 26 s deadline, no key in errors, every scripted mode covered |
| 16 | Local ONNX models | PASS | `test_onnx_models.py`: mean pooling ignores padding, unit vectors, E5 prefixes, CLS pooling, sha256 pin refused on mismatch, S3 download once then verify, cross-encoder scores, router builds the namespace; real bge, e5 and reranker rank the right passage first |
| 17 | Retrieval correctness and pipeline | PASS | `test_retrieval_pipeline.py`: query/passage kinds, same-document dedup only, rerank reorders and renumbers evidence, a failing reranker keeps the fused order, bm25/dense modes |
| 18 | Retrieval benchmark and latency without network | PASS | `evals/run.py --compare` on v1 and the paraphrase set, 3 runs each (BENCHMARKS); bge-small chosen by the pre-set rule; reranker off (fails +150 ms p95) |
| 19 | Workflow Learning Lite | PASS | `test_workflow.py` (20 tests); `evals/workflow_eval.py`: precision 1.0, recall 1.0, support accuracy 1.0, deterministic |
| 20 | Observability | PASS | `test_observability.py`: `/health` providers, audit has environment, providers and `answered_by_model`, the fallback shows in the response and in the structured log, unavailable answers audited with attempts; web `fellBack` test |
| 21 | ADRs, docs, infra | PASS | ADR-017, ADR-018; BENCHMARKS, MILESTONES, PROGRESS, HANDOFF, ARCHITECTURE §11; `cfn-lint` clean; `test_infra.py` (SSM read only for Groq, models/* only, no key or scripted transport in the template) |

Known and not part of this gate:
- Answer quality offline is the scripted extractive rule (answer value match 0.46); reported, never gated.
- The retrieval benchmark's corpus is small (17 chunks in workspace A), so recall@8 is saturated by construction.
- CI's gitleaks job failed on `6ac4715` (B10); later pushes pass. Needs the signed-in job summary.

## M2 Live Gate: GREEN (API 2026-09-19 09:45 IST; browser walk on Amplify 2026-09-19 11:20 IST)

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | ONNX embeddings live; demo documents reach `ready` | PASS | `demo/seed.py` against `https://7qo4ij10i6.execute-api.ap-south-1.amazonaws.com`: 7 documents `ready`, including the PDF; `/health` reports `onnx`, `bge-small-en-v1.5-int8` and index `ok` |
| 2 | Golden question answered by Groq with citations that resolve | PASS (API) | "What is the current submission deadline?": `grounded`, gpt-oss-120b, 22 September cited to the organiser email and the Sync 5 decisions. Browser walk on the Amplify URL: PASS (same answer, 3 citations, citation focuses its passage, injected line not cited) |
| 3 | Live eval: groundedness, recall@8, MRR, latency, fallback rate | PASS | run 2 (`2026-09-19T035434Z-live.json`): security gate passed, value match 1.0, groundedness 1.0, recall@8 1.0, MRR 0.929, p95 answer 1.9 s |
| 4 | Injection with the real model | PASS after a fix | run 1: 0.0 (the model repeated the injected value as a source); fixed in `2577551`; run 2: 1.0 |
| 5 | Reranker on/off and model comparison on the deployed stack | PASS (measured) | the reranker adds about 330 ms at p50 and stays off; 20b alone scores lower than 120b, which stays primary (BENCHMARKS) |
| 6 | Demo PDF ingested and cited live | PASS | `project-brief-v1.pdf`, Page 1, cited for the faculty coordinator (Prof. Meera Kulkarni) |

Found and fixed during the gate:
- ingestion tried to read the Groq key (IAM refused);
- Groq's edge 403s urllib's User-Agent;
- CloudFormation kept old parameter values;
- `ensure_index` ran while the stack was still on Titan, which made a 1,024-d index;
- the model repeated the injected value;
- two eval measurement bugs.

## M2 External Bedrock Gate: superseded by the Live Gate (ADR-017)

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | Titan embeddings live | NOT TESTED | every Bedrock call returns `ValidationException: Operation not allowed`; on-demand quota 0 (re-checked 2026-09-18 15:04 IST) |
| 2 | Answer-model benchmark and ADR-013 decision | NOT TESTED | needs Bedrock |
| 3 | Live eval: recall@8, MRR, groundedness, latency | NOT TESTED | `evals/run.py --api <ApiUrl>` ready; BENCHMARKS row reads "not measured" |
| 4 | Injection with the real model | NOT TESTED | needs Bedrock |
| 5 | Golden question with citations on the deployed URL | PASS (live, 2026-09-19) | Amplify `https://main.d1jy52bqj8dt1h.amplifyapp.com`, Groq + ONNX (ADR-017 replaced Bedrock) |
| 6 | Demo PDF ingested and cited live | NOT TESTED | the PDF path works live up to the embedding call |
