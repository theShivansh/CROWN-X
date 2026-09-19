# CROWN-X benchmarks

Measured results only. Each row records the command, dataset version, commit and date. Method and
gates: `docs/EVALUATION.md`. Offline and live results are separate tables and are never compared or
averaged (ADR-016, ADR-017). Offline answers come from a scripted transport, so they prove pipeline
properties, never model quality. Offline retrieval with a real local model is real retrieval
measured on a laptop, labelled with its model.

## Final evaluation at the freeze (M6, 2026-09-19, product commit `ce1b9be`, tag `freeze-1`)
Everything ran against the frozen product: the deployed stack in ap-south-1 (Groq gpt-oss-120b with a
gpt-oss-20b fallback, ONNX bge-small-en-v1.5 int8, OpenSearch) and the same code offline. Each live
run seeds its own fresh workspaces through the public API, so the demo workspace is untouched.

**Headline** (the numbers the README, writeup and video use):

| Metric | Value | Run |
|---|---:|---|
| Contradiction precision / recall | 1.0 / 1.0 | offline and live (runs 4 and 5) |
| Selection accuracy (current value and rule, 4 keys) | 1.0 | offline and live |
| Format-only differences flagged as conflicts | 0 | offline and live |
| Security gate (citation validity, evidence integrity, isolation, injection, zero model calls) | pass, each 1.0 | offline and live |
| Case pass rate, 40 M2 cases | 0.95 | live run 5 |
| Status accuracy | 0.95 | live run 5 |
| Answer value match | 1.0 | live run 5 |
| Groundedness | 0.964 | live run 5 |
| M3 conflict answers (7 cases) | 7 of 7 | live runs 4 and 5 |
| Retrieval recall@8, golden set v1 | 1.0 | live run 5 |
| Retrieval benchmark v2 (60 passages, 30 queries): recall@5 / recall@8 / MRR | 0.917 / 0.95 / 0.747 | live, 0 errors |
| Query latency inside Lambda, p50 / p95 | 39 / 65 ms | CloudWatch (M4 section) |
| Answer call inside Lambda, p50 / p95 | 731 / 1153 ms | CloudWatch (M4 section) |

**Runs:**

| Run | Command (from `services/api`) | Result file | Notes |
|---|---|---|---|
| Offline gate | `uv run python ../../evals/run.py --offline` | `2026-09-19T144551Z-offline.json` | identical to the M4 baseline: case pass 0.55 (scripted answers), status 0.825, security gate passed, contradictions 1.0 / 1.0 |
| Live 4 | `... --api <ApiUrl> --pace 2.5` | `2026-09-19T145217Z-live.json` | pass 0.90, status 0.925, value match 0.929, groundedness 0.929. **Fallback rate 0.45**: at a 2.5 s pace Groq rate-limited the primary model, and 9 answer calls returned 503 before the runner's retry succeeded |
| Live 5 | `... --api <ApiUrl> --pace 12` | `2026-09-19T150229Z-live.json` | the headline run: fallback 0.0; p50 / p95 query 213 / 250 ms and answer 1068 / 1698 ms, measured by this client, so network included. The misses are `synthesis-06` and `xws-02`, both status only; `xws-02` is the known answer-quality miss from the M2 live gate, not a leak |
| Live retrieval v2 | `... --api <ApiUrl> --retrieval-only --dataset retrieval-v2` | `2026-09-19T151022Z-live-retrieval-v2.json` | 0 errors. By category (recall@5): original 1.0, hard negatives 1.0, Hinglish 1.0, paraphrased 0.875, indirect 0.5. Client p50 / p95 242 / 1191 ms: with 30 samples, one slow request sets p95 |

**A defect found in the first retrieval run, and fixed.** The first live retrieval run at the freeze
(`2026-09-19T144638Z-live-retrieval-v2.json`) recorded `errors: 19`. 19 of its 63 queries got 429s,
from two causes:
- M4's `/query` throttle (3 requests a second);
- the 60 questions per workspace per hour quota: 3 warm-ups + 2 × 30 = 63.

The printed table hid this, and its recall 0.927 / MRR 0.766 were computed over fewer queries than
claimed, so they aren't used. The harness now (a fix after the freeze, in `evals/run.py`):
- paces queries at 0.4 s;
- runs one repeat (33 questions);
- times only the request, not the pacing;
- prints a warning and fails when any query errors.

A second clean run on the same product (`2026-09-19T150813Z-live-retrieval-v2.json`) gave recall 0.917 / 0.95 and MRR 0.769, with latency inflated
by the pacing (fixed before the final run). MRR moves by about 0.02 between fresh workspaces because
of ranking ties.

## M4 latency per stage (deployed stack, CloudWatch Logs Insights)
Measured on 2026-09-19 from the `request finished` and `ingestion stages` log lines, over about three
hours of traffic after deploying `62d5fca`: the security acceptance run, the `@critical` golden path
against Amplify, and the browser walk. The queries are in ARCHITECTURE §6. The times are inside the
Lambda; the browser adds the network round trip. The samples are small, so p95 is close to the max.

| Stage | n | p50 ms | p95 ms |
|---|---:|---:|---:|
| Upload URL (`upload_url`) | 13 | 16 | 24 |
| Upload complete (checksum, enqueue) | 12 | 97 | 132 |
| Query, end to end | 68 | 39 | 65 |
| - question embedding (ONNX bge-small) | 68 | 4 | 5 |
| - BM25 + k-NN search (OpenSearch) | 68 | 13 | 33 |
| - conflict compare | 68 | 0 | 3 |
| Answer call (Groq gpt-oss-120b, incl. retries) | 6 | 731 | 1153 |
| Timeline | 2 | 10 | 23 |
| Documents list | 98 | 7 | 10 |
| Ingestion, end to end | 10 | 927 | 1367 |
| - passage embedding | 10 | 36 | 76 |
| - index write (OpenSearch, refresh) | 10 | 806 | 1246 |
| - claim extraction | 10 | not queried | 19 |

Cold starts show in the small-n routes: `/health` at 2264 ms and one `/conflicts` at 2278 ms were each
a container's first request (model load).

## M3 contradictions (deterministic code, no model; ADR-003, ADR-020)
Measured on 2026-09-19, twice, over the demo corpus (SCENARIO §§2-7, both workspaces). No step makes a
Groq call: `/conflicts` is derived from rule-extracted claims.

**Offline.** Command: `cd services/api && uv run python ../../evals/run.py --offline`.
- Results: `evals/results/2026-09-19T064821Z-offline.json`.
- Code: `a996eec` plus the N3 changes committed as `130e8d2`.

**Live on the deployed stack.**
- `GET /workspaces/{ws}/conflicts` on workspaces seeded fresh by `demo/seed.py` after deploying
  `c6f5702`.
- Workspace A: `ws_KFdHFNj0IPUoOs4pQDcMUQ`. Workspace B: `ws_PHVNGHzyu0EFhrArwFiWvg`.

| Metric | Offline | Live | What it means |
|---|---:|---:|---|
| Contradiction precision | 1.0 | 1.0 | 6 found, 6 expected, 0 false (workspace B: 0) |
| Contradiction recall | 1.0 | 1.0 | every SCENARIO §3 pair |
| Format-equal pairs flagged | 0 | 0 | "22 Sept" = "2026-09-22"; "60 requests per minute" = "60 rpm" |
| Temporal selection accuracy | 1.0 | 1.0 | 4 keys: value and rule (three `newest_source_timestamp`, the owner `latest_upload`) |
| Extraction recall | 1.0 | not measured | 12 of 12 expected claims (`evals/golden/claims-v1.jsonl`); the API has no claims route |
| Extraction precision, confidence 1.0 | 1.0 (6 claims) | 1.0 (6 claims in conflicts) | label forms |
| Extraction precision, 0.90-0.99 | 1.0 (4) | 1.0 (3) | phrases |
| Extraction precision, 0.80-0.89 | 1.0 (2) | 1.0 (1) | a phrase with the year inferred from the document's date (0.81) |
| M3 answers: status accuracy | 0.571 | not run | offline answers are scripted: the 3 misses are `insufficient_evidence` from the extractive mock |

Extraction confidence (ADR-020) is defined as trigger strength × value certainty. The bands have 12
claims between them: every claim in every band was correct, which is a small sample, not a
calibration.

**Change from the M2 baseline** (`2026-09-18T180136Z-offline.json`, same command):
- Every M2 metric is unchanged:
  - case pass rate 0.55; status accuracy 0.825; value match 0.4643; insufficient-evidence
    correctness 0.8;
  - citation validity, evidence integrity, isolation, injection and zero-model-call all 1.0;
  - hit@8 1.0.
- Mock-embedding MRR moved from 0.929 to 0.964. That's the known tie-breaking from random document
  IDs, not an M3 effect.
- Six M2 cases now also accept `conflict`: `synthesis-02`, `synthesis-03`, `distractor-03` and
  `injection-01..03`. Each asks about a fact the sources disagree on, and SCENARIO §8 and §10 require
  the conflict to show.

**The finding that shaped the relevance rule (ADR-020).** The stage prompt attached a conflict whenever
a conflicting claim's chunk was retrieved. On this corpus that flagged almost every question: 17
chunks, top 8, and the brief PDF is one chunk holding two conflicting facts. M2 status accuracy fell
from 0.825 to 0.275 in the first run. A conflict now also needs the question to name the fact, and
status accuracy is back to 0.825.

**Live answer** (one Groq call, in the browser on the Amplify URL):
- The golden question returned `conflict`. The card says "Sources disagree" with 22 Sep 2026 chosen
  by the newest source date.
- The inspector opens on brief v1 against organiser update 3, marked "Newer · 10 Sep".
- gpt-oss-120b cited D1, D3 and D4. Neither 1 October nor 21 September appeared.

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

## Retrieval benchmark v2 (60 passages, 30 queries, passage-level relevance)
Why v2: in golden set v1, workspace A has only 17 chunks, so a top-8 list is nearly half the corpus
and recall@8 saturates. v2 is built to separate the systems.

**Corpus** (`evals/corpus/retrieval-v2/`):
- 12 documents with 5 sections each: brief v2, architecture notes, API spec v2, an SMS vendor quote,
  Sync 6 notes, a volunteer plan, venue logistics, a security review, a QA plan, organiser update 4, a
  sprint retro and budget sheet v3.
- The runner refuses to measure unless the corpus indexes as exactly 60 passages.
- Passages deliberately share vocabulary: at least five deadlines, five limits of one kind or
  another, several budget figures and several owners.

**Queries** (`evals/golden/retrieval-v2.jsonl`), 30 in total:

| Category | Count | What it tests |
|---|---:|---|
| original | 10 | the passage's own words |
| paraphrased | 8 | vocabulary mismatch |
| Hinglish | 6 | code-mixed Hindi-English |
| indirect | 3 | vague "why" or "what if" questions |
| hard negative | 3 | many passages share the words, but only one answers |

**Scoring:**
- Each query lists its relevant passages as `file#section`. A right file with the wrong section
  doesn't count.
- 6 queries have 2 or 3 relevant passages, so recall@5 and recall@8 can differ.
- The corpus and labels were written together and frozen before the first run. Nothing was tuned on
  them. They were written by the same author as the system, which is a known bias.

No answer calls are made, so no Groq quota is used. Commit `0feef94` plus the benchmark files,
2026-09-19.

**Offline, in process:**
- Command: `cd services/api && uv run python ../../evals/run.py --compare --dataset retrieval-v2`
- Index: local BM25Okapi and FAISS on a laptop CPU.
- Each system is asked all 30 queries 3 times after a warm-up. Quality is the mean; the latency
  percentiles pool all 90 timings.
- Results: `evals/results/2026-09-19T052122Z-compare-retrieval-v2.json`

| System | Model | Recall@5 | Recall@8 | MRR | p50 / p95 ms |
|---|---|---:|---:|---:|---:|
| BM25 | none | 0.700 | 0.783 | 0.632 | 5 / 6 |
| dense | e5-small | 0.867 | 0.933 | 0.782 | 9 / 12 |
| hybrid (RRF) | e5-small | 0.900 | 0.933 | 0.710 | 16 / 18 |
| hybrid + rerank | e5-small | 0.933 | 0.933 | 0.856 | 136 / 180 |
| dense | bge-small | 0.867 | 0.883 | 0.839 | 13 / 17 |
| **hybrid (RRF), production** | bge-small | 0.883 | **0.967** | 0.694 | 21 / 24 |
| hybrid + rerank | bge-small | 0.950 | 0.967 | 0.864 | 147 / 183 |

MRR by category, for the bge-small rows. Recall@8 is 1.0 in every category except indirect for all
three rows; indirect is 0.5 for dense and 0.667 for the other two.

| Category | dense | hybrid | hybrid + rerank |
|---|---:|---:|---:|
| original (10) | 1.000 | 0.950 | 1.000 |
| paraphrased (8) | 0.854 | 0.497 | 0.781 |
| Hinglish (6) | 0.556 | 0.708 | 0.889 |
| indirect (3) | 0.667 | 0.500 | 0.444 |
| hard negative (3) | 1.000 | 0.528 | 1.000 |

**Deployed stack:**
- Command: `... --api <ApiUrl> --retrieval-only --dataset retrieval-v2`
- It calls `/query` only: OpenSearch BM25 and HNSW, ONNX bge-small in Lambda, reranker off.
- Latency is measured by the client, so it includes the round trip from this laptop to ap-south-1.
- Results: `evals/results/2026-09-19T052152Z-live-retrieval-v2.json`. An earlier identical run
  (`T051955Z`, since deleted) gave recall@5 0.95, the same MRR, and p50 / p95 206 / 264 ms.

| System | Recall@5 | Recall@8 | MRR | p50 / p95 ms |
|---|---:|---:|---:|---:|
| production hybrid, bge-small | 0.917 | 0.950 | 0.753 | 200 / 242 |

By category on the deployed stack (recall@8 / MRR):

| Category | Recall@8 | MRR |
|---|---:|---:|
| original | 1.0 | 0.950 |
| paraphrased | 1.0 | 0.542 |
| Hinglish | 1.0 | 0.792 |
| indirect | 0.5 | 0.500 |
| hard negative | 1.0 | 0.833 |

What this shows:
- **The answer model sees the right passages.** Production hybrid has the best recall@8, both
  offline (0.967) and deployed (0.950). The answer model reads all 8 passages, so recall@8 is the
  number that limits answer quality.
- **The one live miss is an indirect question.** For `r2-vague-03`, "Is there anything that could stop
  login codes from going out on day one?", the answer is the DLT template registration, and that
  passage never uses the question's words.
- **Equal-weight RRF lowers MRR.** This is now measured on a corpus large enough to show it: hybrid
  MRR 0.694 against dense 0.839 offline. BM25 ranks keyword-heavy distractors first on paraphrases
  and hard negatives. MRR decides which passage is listed first, not what the model reads.
- **The reranker repairs the order but still misses its gate.** It lifts MRR to 0.864 with recall
  unchanged. It costs +126 ms at p50 and +159 ms at p95 over hybrid on a laptop, against the +150 ms
  p95 gate, and it measured +310-345 ms on Lambda earlier. It stays off (ADR-017).
- **Deployed MRR (0.753) is higher than local hybrid (0.694).** The likely cause is that OpenSearch's
  analyzer and BM25 scoring differ from `rank_bm25`. That is not measured separately.
- **Weighted fusion is parked.** Down-weighting BM25 in RRF looks like the fix. Choosing a weight on
  this set would tune on the test set, so it needs a separate development set first (Parking lot).

## Workflow Learning Lite, M5 (labelled synthetic traces; ADR-022)
Command: `cd services/api && uv run python ../../evals/workflows/run.py`, run twice with
byte-identical output. 20 seeded scenarios from `evals/workflows/generate.py`, each with:
- two planted workflows (a 5-step "sprint review" with the new UI steps, sometimes twice in one
  session; a 4-step "intake");
- near misses: swapped steps, and a step missing;
- an interrupted review, with an extra step in the middle;
- step-free system events, double-clicks and 5 retried writes;
- one-offs.

| Metric | First run (ADR-018 rule) | After the fragment rule (ADR-022) |
|---|---:|---:|
| Pattern precision | 0.4 | 1.0 |
| Pattern recall | 1.0 | 1.0 |
| False-suggestion rate | 0.6 (60 of 100) | 0.0 (0 of 40) |
| Support-count accuracy | 1.0 | 1.0 |
| Deterministic | yes | yes |

**Every false suggestion from the first run, reviewed by hand:**

| Suggestion | In how many scenarios | Why it appeared |
|---|---:|---|
| ask → read → inspect conflict | 20 | the sprint review's start; the two "step missing" near misses also start this way, so support = review + 2 |
| inspect conflict → open timeline → copy | 20 | the review's tail; the interrupted review also ends this way (+1) |
| ask → read → open passage | 20 | the intake's tail; the interrupted review contains it (+1) |

Each is a correct observation, but it's a fragment of a workflow already suggested, not a workflow of
its own. It also ranked above the full workflow by support. The fragment rule keeps a sub-sequence
only if it also happened `min_support` times on its own. A unit test shows the other side: a
fragment with 3 extra occurrences is still suggested.

This is our own synthetic benchmark, so 1.0 shows that the rules do what they say. It doesn't show
the suggestions are useful.

**Live demo trace** (2026-09-19, workspace A):
- The real UI was driven through "prepare sprint review" three times: 12 client events, all 201.
- Refresh found the 6-step routine with support 3. Groq named it "Answer Review Workflow", given step
  types and relative times only.
- The card says "Finished 3 of the 8 times it started with 'ask a question'": workspace A has other
  questions from earlier golden-path runs.

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
Stack `crownx`, ap-south-1: Lambda arm64 at 2,048 MB, OpenSearch `crownx-chunks-384`, embeddings
`bge-small-en-v1.5` int8 in Lambda, Groq answers. Dataset `evals/golden/v1.jsonl`: 40 M2 cases, with
the 7 M3 cases excluded. Each run seeds fresh workspaces through the public API.

| Run | Date (UTC) | Commit | Answer model | Security gate | Injection | Value match | Groundedness | Pass rate | Recall@8 | MRR | Fallback | p50 / p95 query | p50 / p95 answer |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1, first live | 2026-09-18 19:43 | `5340857` | gpt-oss-120b, falls back to 20b | **failed** | **0.0** | 0.893 | 0.821 | 0.85 | 1.0 | 0.911 | 0.25 | 211 / 402 ms | not valid (timer bug) |
| 2, after the injection fix | 2026-09-19 03:54 | `2577551` | gpt-oss-120b, falls back to 20b | passed | 1.0 | 1.0 | 1.0 | 0.975 | 1.0 | 0.929 | 0.025 | 196 / 760 ms | 917 / 1,856 ms |
| 3, model benchmark | 2026-09-19 04:14 | `2577551` | gpt-oss-20b only | passed | 1.0 | 0.929 | 0.929 | 0.925 | 1.0 | 0.911 | 0 | 178 / 214 ms | 741 / 887 ms |

Results files, all in `evals/results/`: `2026-09-18T194300Z-live.json`, `2026-09-19T035434Z-live.json`
and `2026-09-19T041426Z-live.json`.

**Run 1**, paced at 8 s. It found three problems:
- **Injection, a real finding.** In all 3 cases gpt-oss-120b reported the injected "1 October" as a
  disagreeing source ("a pasted chat message claims..."). It never obeyed the line, but it repeated
  its value. The fix, in `2577551`, has two parts:
  - The prompt now says an instruction line is not a source.
  - `finalize()` drops any claim whose only citations carry text addressed to an assistant. In run 2
    the backstop dropped nothing; the prompt alone was enough. The backstop is covered by unit tests
    but untested on live traffic.
- **Value-match misses, a measurement bug.** gpt-oss writes "4 KB" and "21 September" with a narrow
  no-break space (U+202F). Matching now normalizes with NFKC.
- **Answer latency, a measurement bug.** The timer included the pacing sleep, so run 1's answer
  latency isn't reported.

**Run 2**, paced at 12 s. The one failure is `xws-02`. Asked about MessMate in the FestPass
workspace, the model answered with FestPass's deployment owner instead of saying the documents
don't cover it. It's an answer-quality miss, not a leak: isolation is 1.0, and no MessMate text was
retrieved.

**Run 3:** gpt-oss-20b alone is about 20% faster at p50, but misses more values: `lookup-03`
(the 429 backoff) and `injection-03` (it gave the date in another format). It stays the fallback.

Rate limits: at an 8 s pace, a quarter of the answers came from the fallback. At 12 s, 1 in 40 did.

**Reranker on the deployed stack** (retrieval only, no answer calls,
`evals/run.py --api <ApiUrl> --retrieval-only`; results `2026-09-19T040018Z-live-retrieval.json` for
off and `...T040314Z-live-retrieval.json` for on):

| Reranker | v1 MRR | v1 p50 / p95 | paraphrase MRR | paraphrase recall@8 | paraphrase p50 / p95 |
|---|---:|---:|---:|---:|---:|
| off | 0.929 | 213 / 472 ms | 0.637 | 0.893 | 189 / 227 ms |
| on (top 8) | 1.000 | 523 / 556 ms | 0.741 | 0.893 | 535 / 568 ms |

The reranker improves ranking but adds about 310-345 ms at p50 on Lambda. On the paraphrase set its
p95 grows by 341 ms, which fails the +150 ms rule, so it stays off (ADR-017). Recall@8 doesn't change,
so the answer model sees the same passages.

What the live columns mean:
- **Groundedness:** the exact proxy, meaning the share of answered cases whose claims all cite given
  evidence and contain the expected values. A model-graded check needs its 10-case hand-checked
  agreement first (EVALUATION §3).
- **Fallback rate:** the share of answers written by the fallback model.

Gates are proposed from this live run, not from the offline one.
