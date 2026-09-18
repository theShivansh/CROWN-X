# CROWN-X benchmarks

Measured results only. Each row records the command, dataset version, commit and date. Method and
gates: `docs/EVALUATION.md`. Offline and live results are separate tables and are never compared or
averaged (ADR-016, ADR-017). Offline answers come from a scripted transport, so they prove pipeline
properties, never model quality. Offline retrieval with a real local model is real retrieval
measured on a laptop, labelled with its model.

## M2 offline gate, after ADR-017 (Groq adapter over the scripted transport; local index)
Command: `cd services/api && uv run python ../../evals/run.py --offline [--embedding <model>]` ·
dataset `evals/golden/v1.jsonl` (47 cases: 40 M2, 7 M3) · commit `fbe3dea` · 2026-09-18 18:01 UTC.

Setup for both runs:
- The real API handlers, in process.
- Answers: the production `GroqAnswerer` for `openai/gpt-oss-120b` over `MockGroqTransport` (scripted,
  no network).
- Index: a local BM25Okapi + FAISS `IndexFlatIP`.
- Storage: in memory.

| Metric | mock embeddings | e5-small (real model) | What it means |
|---|---:|---:|---|
| Citation validity | 1.0 | 1.0 | every cited ID was in the evidence given |
| Evidence-ID integrity | 1.0 | 1.0 | every chunk belongs to the asked workspace |
| Workspace isolation (7) | 1.0 | 1.0 | no cross-workspace value or file |
| Injection resistance (3) | 1.0 | 1.0 | the injected dates never appear in an answer |
| Zero-model-call path (2) | 1.0 | 1.0 | empty workspace: no model call, `insufficient_evidence` |
| Security gate | passed | passed | |
| Retrieval hit rate at 8 | 1.0 | 1.0 | |
| Retrieval MRR | 0.929 | 0.946 | mock: **not semantic**; e5: real local embeddings |
| Answer value match | 0.4643 | 0.4643 | scripted extractive answers; **not model quality** |

Results: `evals/results/2026-09-18T180136Z-offline.json` (mock) and `...T180140Z-offline.json` (e5).
The answer rows equal the M2 baseline below because the scripted transport reuses the extractive rule.

## Retrieval comparison (local models, measured on a laptop CPU)
Command: `cd services/api && uv run python ../../evals/run.py --compare [--dataset paraphrase]`.

Method:
- Each configuration re-ingests the demo corpus into a fresh local index.
- It asks every M2 case that has relevant files, and runs 3 times; the table shows means and the MRR
  range. Document IDs are random, so exact score ties can break differently.
- Dense and hybrid use the model shown. Reranking rescores the top 8 fused candidates with
  `ms-marco-MiniLM-L-6-v2` int8.
- Latency is stage-1 retrieval in process, not Lambda.
- Commit `fbe3dea`, plus the "rerank the top 8" change committed right after.
- Results: `evals/results/2026-09-18T175330Z-compare-v1.json` and `...T175608Z-compare-paraphrase.json`.

**Golden set v1** (28 answerable M2 cases; the questions mostly reuse the documents' words):

| System | Model | Hit@8 | Recall@5 | Recall@8 | MRR (range) | p50 / p95 ms |
|---|---|---:|---:|---:|---:|---:|
| BM25 | none | 1.0 | 0.988 | 1.0 | 0.964 (0.964-0.964) | 2 / 3 |
| dense | e5-small | 1.0 | 0.988 | 1.0 | 0.946 (0.946-0.946) | 10 / 12 |
| hybrid (RRF) | e5-small | 1.0 | 0.988 | 1.0 | 0.952 (0.946-0.964) | 15 / 18 |
| hybrid + rerank | e5-small | 1.0 | 1.0 | 1.0 | 1.000 | 373 / 483 |
| dense | bge-small | 1.0 | 0.988 | 1.0 | 0.864 (0.864-0.864) | 15 / 19 |
| hybrid (RRF) | bge-small | 1.0 | 0.988 | 1.0 | 0.917 (0.905-0.923) | 15 / 21 |
| hybrid + rerank | bge-small | 1.0 | 1.0 | 1.0 | 1.000 | 312 / 532 |

**Paraphrase set** (`evals/golden/paraphrase-v1.jsonl`, 14 cases):
- The same answers as v1 cases, asked in other words; 4 of the questions are Hinglish.
- Written for this comparison to test vocabulary mismatch, and never used to tune anything.

| System | Model | Hit@8 | Recall@5 | Recall@8 | MRR | p50 / p95 ms |
|---|---|---:|---:|---:|---:|---:|
| BM25 | none | 0.857 | 0.714 | 0.786 | 0.619 | 2 / 2 |
| dense | e5-small | 0.929 | 0.679 | 0.929 | 0.614 | 9 / 12 |
| hybrid (RRF) | e5-small | 0.929 | 0.714 | 0.929 | 0.572 | 10 / 12 |
| hybrid + rerank | e5-small | 0.929 | 0.857 | 0.929 | 0.741 | 346 / 479 |
| dense | bge-small | 1.0 | 0.893 | 1.0 | 0.766 | 11 / 14 |
| hybrid (RRF) | bge-small | 0.929 | 0.857 | 0.929 | 0.661 | 15 / 18 |
| hybrid + rerank | bge-small | 0.929 | 0.893 | 0.929 | 0.741 | 430 / 630 |

Hinglish subset (4 of the 14 cases, one run):

| System | MRR | Hit@8 |
|---|---:|---:|
| BM25 | 0.625 | 0.75 |
| hybrid, e5-small | 0.619 | 1.0 |
| hybrid, bge-small | 0.833 | 1.0 |

What this shows, and what it doesn't:
- **Keyword questions are easy on this corpus.** On v1, BM25 alone is the best single retriever.
  Workspace A holds only 17 chunks, so a top-8 list is nearly half the corpus: recall@8 is saturated
  by construction, and only MRR separates the systems. A bigger corpus is needed before any of these
  numbers generalize.
- **Semantic retrieval pays off when the words differ.** On paraphrases, BM25 misses the relevant
  file in 2 of 14 top-8 lists; dense bge finds all of them.
- **Plain RRF doesn't always beat its better half.** On paraphrases, hybrid MRR is below dense MRR,
  because equal-weight fusion lets BM25's misses push the right passage down.
- **The reranker restores the order but is too slow for its gate.** It lifts MRR everywhere, yet costs
  about 300-600 ms p95 here, against the pre-set gate of +150 ms p95. Recall@8 doesn't change, so the
  answer model sees the same passages. It stays off in production (ADR-017).
- **Production embeds with bge-small**, by the pre-set rule (better MRR, no worse recall@8).
  Combined hybrid MRR over both sets is 0.832 for bge against 0.825 for e5. The margin is small and
  the sets are small (42 cases), so this is a measured default, not a general finding.

## Workflow Learning Lite (synthetic traces; ADR-018)
Command: `cd services/api && uv run python ../../evals/workflow_eval.py` · 20 seeded scenarios. Each
scenario plants 3 to 5 repeats of a true workflow and adds:
- near-miss reorderings;
- one-off sequences;
- unrelated system events;
- 5 duplicated events.

| Metric | Value |
|---|---:|
| Pattern precision | 1.0 |
| Pattern recall | 1.0 |
| False suggestions | 0 |
| Support-count accuracy | 1.0 |
| Deterministic (same output for reversed input) | yes |

The first run scored precision 0.33: alternating ask/read fragments outranked the planted workflow.
The rule "at least 3 different steps" was then added (ADR-018). The traces are ours and synthetic, so
this shows that the miner does what its rules say, not that its suggestions help anyone.

## M2 offline baseline, before ADR-017 (deterministic; MockProvider)

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

## Live baseline (M2 live gate: deployed stack, Groq + ONNX)
| Run | Date | Commit | Dataset | Recall@8 | MRR | Groundedness | Fallback rate | p50 / p95 query | p50 / p95 answer | Models |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| live baseline | not run | none | v1 | not measured | not measured | not measured | not measured | not measured | not measured | gpt-oss-120b, bge-small |

Run after deploying: `cd services/api && uv run python ../../evals/run.py --api <ApiUrl> --pace 2.5`
(paced for Groq's free tier; a 503 `answer_unavailable` is retried after a pause).

What the live columns mean:
- **Groundedness:** the exact proxy, meaning the share of answered cases whose claims all cite given
  evidence and contain the expected values. A model-graded check needs its 10-case hand-checked
  agreement first (EVALUATION §3).
- **Fallback rate:** the share of answers written by the fallback model.

Gates are proposed from this live run, not from the offline one.
