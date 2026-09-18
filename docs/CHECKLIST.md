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

Known and not part of this gate:
- Mock answer quality is low by design (answer value match 0.46); it is reported, never gated.
- CI's gitleaks job failed on `6ac4715` (B10); later pushes pass. Needs the signed-in job summary.

## M2 External Bedrock Gate: BLOCKED (B4)

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | Titan embeddings live | NOT TESTED | every Bedrock call returns `ValidationException: Operation not allowed`; on-demand quota 0 (re-checked 2026-09-18 15:04 IST) |
| 2 | Answer-model benchmark and ADR-013 decision | NOT TESTED | needs Bedrock |
| 3 | Live eval: recall@8, MRR, groundedness, latency | NOT TESTED | `evals/run.py --api <ApiUrl>` ready; BENCHMARKS row reads "not measured" |
| 4 | Injection with the real model | NOT TESTED | needs Bedrock |
| 5 | Golden question with citations on the deployed URL | NOT TESTED | needs Bedrock and Amplify (M1 S6) |
| 6 | Demo PDF ingested and cited live | NOT TESTED | the PDF path works live up to the embedding call |
