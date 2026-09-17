# CROWN-X evaluation plan

A demo that looks good once is not evidence. Every quality claim in the README, writeup or video comes
from a recorded run in `docs/BENCHMARKS.md` (command, dataset version, commit, date). A value that
hasn't been measured is written as "not measured".

## 1. Golden dataset (`evals/golden/`, versioned)
Hackathon size: 40-60 questions over 6-10 seeded project documents. Portfolio size later: 100-200.

| Category | What it tests |
|---|---|
| exact lookup | one source, one value |
| multi-document synthesis | answer needs two sources |
| version-sensitive | older and newer sources disagree; the newer should be selected |
| date conflict / numeric conflict / owner conflict | contradiction detection |
| equal values, different formats | "22 Sept" vs "2026-09-22": must **not** be a conflict |
| missing timestamps | selection falls back by rule, or doesn't select |
| no-answer | nothing relevant indexed: insufficient evidence |
| distractor-heavy | similar but irrelevant passages |
| injection | a document instructs the model to ignore rules or change format |
| cross-workspace | the answer exists only in another workspace: must not appear |

Each case records `question`, `workspace`, `expected_status`, `expected_values`,
`expected_evidence_chunk_ids`, `expected_conflict` (pair and type) and `category`.

## 2. Metrics
- **Retrieval:** recall@k, MRR, evidence hit rate.
- **Grounding:** citation precision (cited chunks support the claim), citation completeness,
  unsupported-claim rate, and insufficient-evidence correctness.
- **Contradictions:** precision, recall, F1, false-conflict rate (format-only differences count as
  false).
- **Temporal:** current-value selection accuracy, correct rule named.
- **Robustness:** pass rate on injection and cross-workspace cases (target: all pass, as these are
  security properties).
- **System:** p50 and p95 per stage (upload, ingestion, retrieval, generation, end to end), error rate.

## 3. Method
- Exact checks wherever possible: IDs, statuses, normalized values, conflict pairs.
- A model grader only for "does this sentence follow from this passage", recording the grader prompt,
  rubric, model ID and a hand-checked sample of 10 to estimate its agreement.
- Record a baseline before optimizing, and compare before and after on the same dataset version.
- Report the worst failures with their case IDs, not only averages.

## 4. Gates (set after the M2 baseline, recorded in DECISIONS)
Release is blocked if:
- any injection or cross-workspace case fails;
- citation precision drops below the recorded gate;
- contradiction precision drops below the recorded gate (a false conflict on screen undermines the
  product);
- a metric regresses beyond the tolerance agreed at baseline;
- tests fail.

Gate values are chosen from the measured baseline, never picked in advance.

## 5. Calibration
No confidence number reaches the UI in the hackathon build. If one is added later, bin confidence
against measured correctness first and show only what the bins support.

## 6. Workflow Learning Lite (M5)
Synthetic event traces with repeated true workflows, near-miss sequences, reorderings, duplicates,
unrelated interleavings and one-off sequences. Metrics: pattern precision and recall, false-suggestion
rate, support-count accuracy, determinism (identical output for identical input). Release gate: every
surfaced suggestion traces to concrete events, and the false suggestions on the benchmark were
inspected by hand.

## 7. Results table (`docs/BENCHMARKS.md`)
| Run | Commit | Dataset | Recall@8 | Citation precision | Contradiction F1 | Temporal accuracy | p95 end to end |
|---|---|---|---:|---:|---:|---:|---:|
| baseline | not run | v1 | not measured | not measured | not measured | not measured | not measured |

## 8. Portfolio ablations (post-hackathon)
A semantic only · B hybrid · C hybrid + reranker · D hybrid + reranker + metadata-aware ranking.
Record quality and latency for each.
