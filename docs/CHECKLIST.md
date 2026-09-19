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

## M6 Freeze and submit: freeze part GREEN (2026-09-19 21:00 IST, `freeze-1` = `ce1b9be`); video and submission OPEN

| # | Gate / item | Result | Evidence |
|---|---|---|---|
| 1 | Freeze tagged | PASS | `freeze-1` on origin at `ce1b9be`; later changes are docs or the logged eval-harness fix |
| 2 | Final eval recorded | PASS | BENCHMARKS "Final evaluation at the freeze": offline gate; live runs 4 (2.5 s pace) and 5 (12 s pace); live retrieval v2 with 0 errors. The first retrieval run's 19 errors are disclosed |
| 3 | Golden path live at 1440x900 and 1024x768 | PASS | scripted keyboard-only walk on Amplify: the conflict answer, Tab to the timeline, arrow keys, focus ring, no overflow, console clean (1024 with reduced motion) |
| 4 | Diagnosis drill | PASS | 404 request ID `req_D873hhgQBcwEJCw=` found in Logs Insights (`request finished` 404 `not_found`) |
| 5 | M5 flag state | PASS | flags on, as decided; card live in workspace A |
| 6 | README, CREDITS, WRITEUP | PASS | product README with screenshots from the deployed site, architecture as built, measured table from BENCHMARKS; CREDITS names Claude Code (Opus 5) and GitHub Copilot, models and licences read from metadata |
| 7 | Repository public, history in window, CI and gitleaks green | pending the final push | first commit 2026-09-17 13:18 IST; no force-push |
| 8 | Video recorded and checked | OPEN | the user records from `docs/VIDEO_TAKE_SHEET.md` |
| 9 | Submitted, recorded in PROGRESS | OPEN | the user submits from `docs/SUBMISSION.md` |

## M5 Workflow Learning Lite: GREEN (2026-09-19 20:15 IST, deployed `8e2fbef`, flags on)
Verified with `/verify-stage M5`.

| # | Gate / item | Result | Evidence |
|---|---|---|---|
| 1 | Scope | PASS | `81ae701..8e2fbef` touch workflow events, the miner, the workflow API and card, the benchmark, tests and docs only |
| 2 | Determinism, support, duplicates (unit) | PASS | `test_workflow.py` 25 tests (session gap at exactly 30:00 and 30:01, fragments, confidence, byte-identical output); `test_workflow_api.py` 16 tests (retry stored once, flag off 404 everywhere, server-owned types refused, IDs only, quota, scoping, naming once, fallback, versions, dismiss) |
| 3 | Events, refresh, suggestion, save, dismiss (integration) | PASS | `services/api/tests/integration/test_workflows.py` on the deployed stack: support 3, save v1 then v2, dismissal hides it, a retry recorded once, another workspace 404 |
| 4 | Card explains its events on the deployed URL (live) | PASS | the real UI driven three times in workspace A. The card shows "Answer Review Workflow" (Groq), 6 steps, "3 times", "Why detected?" in counts. The detail lists the 3 matching occurrences with times |
| 5 | Golden path with the flag on (live) | PASS | `@critical` golden path against Amplify (flag on); CI e2e builds with the flag on (7 tests) |
| 6 | Benchmark recorded, false suggestions reviewed | PASS | BENCHMARKS "Workflow Learning Lite, M5": precision 0.4 → 1.0 after the fragment rule, recall 1.0, support 1.0, deterministic; each false suggestion explained |
| 7 | Quality | PASS | API 343 passed (6 integration skipped without `EVAL_API_URL`); ruff; web lint, typecheck, 28 unit tests, build, 7 e2e; `cfn-lint`; CI green on `8e2fbef` |
| 8 | Security | PASS | events hold IDs only (validated, text refused); server-owned types refused; quota; flag off leaves nothing reachable; the model sees step types and times only, and its reply is validated |
| 9 | Observability | PASS | `workflow suggestions refreshed` and `workflow saved` log lines; every request's `request finished` line |

Found and fixed: client events keyed by the browser clock mis-ordered steps (now server time, ADR-022);
fragments of a workflow outranked it on the card (fragment rule).

## M4 Timeline, polish, reliability: GREEN (2026-09-19 18:55 IST, deployed `62d5fca`)
Verified with `/verify-stage M4`.

| # | Gate / item | Result | Evidence |
|---|---|---|---|
| 1 | Scope | PASS | `9227742..bb6be5e` touch the timeline, limits, logs, the workspace UI, tests and docs only |
| 2 | Timeline with the conflict marked (live) | PASS | `GET /timeline` on workspace A: brief v1 20 Sep, update 3 22 Sep (changed), Sync 5 (current, newest source date); the UI track with the dashed conflict segment at 1440 and 1024 on Amplify |
| 3 | UI_UX §3 states, ANTI_SLOP §6 (live) | PASS | scripted keyboard-only walk on Amplify at 1440 and at 1024 with reduced motion: palette, conflict card, inspector, timeline by Tab and arrow keys, focus ring, no horizontal overflow, console clean. Error, insufficient, limit, failed-ingestion and reduced-motion states in the `@critical` suite |
| 4 | Failed request traced by request ID (integration) | PASS | "Workspace not found" in the UI showed `req_D8q_fhV_hcwEPrw=`; Logs Insights found its `request finished` (404, `not_found`) and `request rejected` lines in 5 s |
| 5 | Security T1-T3, T5-T7 (integration); T4 reviewed | PASS | integration suite against the deployed stack, all pass; T4 review in SECURITY §6. T1's first version found the same-passage refusal (README limitation) |
| 6 | `@critical` Playwright in CI and once live | PASS | CI job green on `62d5fca` (6 tests); golden path against Amplify passed |
| 7 | Golden path without a manual step (live) | PASS | the live `@critical` run and the walk |
| 8 | p50 and p95 per stage in BENCHMARKS | PASS | BENCHMARKS "M4 latency per stage" |
| 9 | Quality | PASS | API 322 passed, 5 integration skipped without `EVAL_API_URL`; ruff; web lint, typecheck, 24 unit tests, build; harness 39; `cfn-lint` |
| 10 | Observability | PASS | every request logs route, status, error code and stage times; ingestion logs its stages (its INFO lines didn't reach CloudWatch before M4: fixed) |

Deviations (ADR-021): no reserved concurrency (account limit 10); the model-timeout path is tested by
the scripted transport and a recorded 504, not on a dev stack. Landing page not built (optional).

## M3 Contradictions: GREEN except the demo recording (2026-09-19 13:40 IST, deployed `09afe27`)
Verified with `/verify-stage M3`. The one open item is the rough demo recording, which the user records
(the script is in PROGRESS).

| # | Gate / item | Result | Evidence |
|---|---|---|---|
| 1 | Scope | PASS | `5d36e76..09afe27` touch only claims, conflicts, their API, the eval, the inspector UI, IAM for claim writes, the `/conflicts` route and docs |
| 2 | Date, numeric and owner conflicts; format-only never (unit) | PASS | `test_claims.py` (30 tests): normalization ("22 Sept" = 2026-09-22, 60 rpm = 60 requests per minute, ₹50,000 = INR 50000, 09/10/2026 ambiguous), extraction on the six demo files, predicate, stable IDs, the injection line and the distractor |
| 3 | Selection names the rule; no signal means no selection (unit) | PASS | `test_claims.py`: newest source date, version order within a family, latest upload, no upload time, a tie on the rule |
| 4 | Exactly the scenario's conflicts (integration) | PASS | offline eval 6/6 pairs, 0 false, format-equal 0 (`2026-09-19T064821Z-offline.json`); live `GET /conflicts` on fresh workspace A: 4 groups, 6 pairs, every selection right; workspace B: 0 |
| 5 | Contradiction precision and recall recorded (integration) | PASS | BENCHMARKS "M3 contradictions": precision 1.0, recall 1.0, selection accuracy 1.0, extraction precision 1.0 in every confidence band, recall 1.0 |
| 6 | Deadline conflict in the inspector on the deployed URL (live) | PASS | In the browser on `https://main.d1jy52bqj8dt1h.amplifyapp.com/app/?ws=ws_KFdHFNj0IPUoOs4pQDcMUQ`, the golden question gives:<br>- the "Sources disagree" card, from data;<br>- the inspector with brief v1 (20 Sep) against organiser update 3 (22 Sept), marked "Newer · 10 Sep";<br>- the rule "newest source date";<br>- the timeline 31 Aug → 10 Sep (changed) → 11 Sep (current value);<br>- a gpt-oss-120b answer citing D1, D3 and D4, with no 1 October or 21 Sept. |
| 7 | Rough demo recording | DEFERRED to M6 | the user chose to record once at the freeze (2026-09-19); script in PROGRESS |
| 8 | Quality | PASS | API `uv run pytest -q` 309 passed (5 consecutive runs), `ruff` clean, `uv lock --check` ok; harness 39 passed; web lint, typecheck, `pnpm test` 18 passed, `pnpm build` ok; `cfn-lint` clean |
| 9 | Evaluation vs the M2 baseline | PASS | every M2 metric unchanged (case pass 0.55, status 0.825, value match 0.4643, security properties 1.0); the contradiction precision gate (1.0) now fails `evals/run.py` otherwise |
| 10 | Security | PASS | the conflicts block is escaped data (`test_the_conflicts_block_is_escaped_data_like_the_evidence`); conflicts never cross workspaces (test and live B = 0); the injected line never becomes a claim; the ingest role gained only `Query` and `BatchWriteItem` on the table |
| 11 | Observability | PASS | `/conflicts` returns `request_id`; ingestion logs `claims extracted` per document (keys, minimum confidence); the answer audit and the "answer written" log carry conflict IDs, extraction confidence and the selection rule (`test_conflicts_api.py`) |
| 12 | Docs | PASS | ADR-020; SRS §4 and ARCHITECTURE §4 updated; README limitation; BENCHMARKS M3 section |
| 13 | Demo path without a manual step | PASS | `demo/seed.py`, then the golden question on the Amplify URL |

Found and fixed during verification:
- **The first deploy failed ingestion.** Claim queries passed low-level `{"S": ...}` values, which the
  resource client refuses. My test double had copied the same mistake, so the tests missed it. Fixed in
  `c6f5702`, and the double now refuses them too.
- **A flaky `latest_upload` selection.** Two uploads could share a timestamp on a coarse clock, and a
  tie correctly selects nothing. Timestamps now strictly increase within a process (`09afe27`).

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
