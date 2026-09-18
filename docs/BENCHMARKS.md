# CROWN-X benchmarks

Measured results only. Each row records the command, dataset version, commit and date. Method and
gates: `docs/EVALUATION.md`. Offline (mock) and live (Bedrock) results are separate tables and are
never compared or averaged (ADR-016): the offline run proves pipeline properties, not model quality.

## M2 offline baseline (deterministic; MockProvider)
Command: `cd services/api && uv run python ../../evals/run.py --offline` · dataset `evals/golden/v1.jsonl`
(47 cases: 40 M2, 7 M3) · commit `551708a` · 2026-09-18 11:20 UTC · results
`evals/results/2026-09-18T112032Z-offline.json`. Providers: `test` environment, answers `mock`
(`mock-extractive`), embeddings `mock` (`mock-hashed-bow`), in-memory storage, real API handlers.

| Metric | Value | What it means here |
|---|---:|---|
| Citation validity | 1.0 | every cited evidence ID was in the evidence the answer was given |
| Evidence-ID integrity | 1.0 | every evidence chunk belongs to a document in the asked workspace |
| Workspace isolation (7 cases) | 1.0 | no workspace-B value or file in workspace-A answers or evidence, and the reverse |
| Injection resistance (3 cases) | 1.0 | "1 October" (and the distractor dates) never in an answer |
| Zero-model-call path (2 cases) | 1.0 | empty workspace: `insufficient_evidence`, `answer_provider` null |
| Security gate | passed | all five rows above at 1.0 |
| Insufficient-evidence correctness (5 cases) | 0.8 | mock only; not model quality |
| Status accuracy (40 cases) | 0.825 | mock only |
| Answer value match (28 answerable cases) | 0.4643 | extractive mock picks sentences by word overlap; not model quality |
| M2 case pass rate | 0.55 | all checks on a case at once; dominated by mock answer quality |
| Retrieval hit rate at 8 | 1.0 | lexical BM25 + mock hashed embeddings; **not semantic retrieval** |
| Retrieval MRR | 0.887-0.946 over 5 runs | same caveat; varies because tie-breaks follow random document IDs |

Worst M2 failures (all answer quality under the mock, none security): `lookup-01` (picked the
programme sentence, not the faculty-coordinator line), `lookup-03` (picked the Events Portal intro
over the 429 rule), `lookup-05` (picked the badge-printing note instead of the table row). Tables and
lists are where word-overlap extraction does worst.

M3 cases (7: date, numeric, owner, version, missing-timestamp, two format-equal) are excluded from
every M2 number and expected to fail until claims and conflicts ship.

## Live baseline (Bedrock; external gate, blocked by B4)
| Run | Date | Commit | Dataset | Recall@8 | MRR | Groundedness | p50 / p95 query | p50 / p95 answer | Answer model |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| live baseline | not run | none | v1 | not measured | not measured | not measured | not measured | not measured | ADR-013 proposed |

Run when Bedrock is enabled: `cd services/api && uv run python ../../evals/run.py --api <ApiUrl>`
against a stack deployed with `AnswerModelId` set. Groundedness needs the model grader and its
10-case hand-checked agreement first (EVALUATION §3). Gates are proposed from this live run, not from
the offline one.
