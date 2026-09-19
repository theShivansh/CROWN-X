# README media assets

Every image in the README is either captured from the deployed app or generated from the measured
tables in `docs/BENCHMARKS.md`. There are no mockups or placeholders. Captures are from 19 September
2026, on `https://main.d1jy52bqj8dt1h.amplifyapp.com/` with demo workspace A
(`ws_KFdHFNj0IPUoOs4pQDcMUQ`), at 1440x900 in the dark theme.

## Captured from the deployed app (Playwright)

| File | What it shows | How it's captured |
|---|---|---|
| `demo-hero.gif` | Ctrl+K → the golden question → the cited answer with "Sources disagree" → a citation opens its passage → the conflict inspector and "Why was this flagged?" → the full timeline → the workflow detail. 109 frames, about 24 s, 960x600 | frames from `capture-media.mjs`, assembled by `scripts/build_demo_gif.py` |
| `hero-dashboard.png` | The whole workspace after the answer: documents with conflict counts, the answer, the conflict card and the evidence panel | full viewport, after the answer settles |
| `evidence-chat.png` | The answer card: "Sources disagree", the current value and rule, sentences with citation chips, Copy answer, and the model that answered | the `region "Answer"` element |
| `conflict-inspector.png` | Brief v1 (20 Sep) against organiser update 3 (22 Sep, marked "Newer · 10 Sep") | the `region "Conflict inspector"` element |
| `timeline-view.png` | 20 Sep 2026 → 22 Sep 2026 across 3 sources, with the dashed conflict segment and the current value | the timeline region, after "Open the full timeline" |
| `workflow-learning-card.png` | "Answer Review Workflow": 6 steps, 3 times, Save and Dismiss | `section[aria-labelledby=workflow-heading]` |
| `workflow-detail-dialog.png` | The 6 steps, and the 3 matching occurrences with their timestamps | full viewport, after "See the events behind it" |
| `upload-flow.png` | The documents rail: the upload dropzone, and 6 ready documents with passage and conflict counts | the `navigation "Documents"` element, cropped to 860 px high |
| `error-request-id.png` | "Workspace not found" with its request ID, the start of the CloudWatch drill | full viewport of `/app/?ws=ws_videoDrillNotFound0000` |

To recapture them all:

```bash
cd apps/web && node e2e/capture-media.mjs ../../.media-capture
```

```bash
python scripts/build_demo_gif.py .media-capture
```

Then copy the PNGs you want from `.media-capture/` into `docs/media/`. Crop `upload-flow.png` to 860 px
high, since the rail element is as tall as the viewport.

- **It asks one real question.** That's one Groq call, and 1 of workspace A's 60 questions for the
  hour. It also adds events, so the workflow card's "Finished 3 of the N times" count goes up. Don't
  run it just before recording the video.
- **Behind a proxy that intercepts TLS**, set `HTTPS_PROXY`: the script passes it to Chromium.
- The capture script isn't a Playwright test (`testMatch` only picks up `*.spec.ts`), so CI never runs
  it.

## Generated from measured numbers

`python scripts/readme_media.py` writes all of these. Each chart's numbers sit in that script, next
to the BENCHMARKS section they come from.

| File | Content | Source in `docs/BENCHMARKS.md` |
|---|---|---|
| `banner.svg` | Title, tagline, the three rules, the golden conflict | the demo scenario |
| `architecture-overview.svg` | The deployed architecture: Amplify, API Gateway, two Lambdas, S3, OpenSearch, DynamoDB, Groq (outside AWS), CloudWatch | ARCHITECTURE §2 as built |
| `retrieval-pipeline.svg` | The ingest, retrieve and answer stages, including the reranker (built, off) | ADR-009, ADR-017, ADR-020 |
| `benchmark-chart-recall.svg` | Recall@5 and recall@8 for BM25, dense, hybrid, hybrid + rerank (offline), and hybrid live | "Retrieval benchmark v2" and "Final evaluation at the freeze" |
| `benchmark-chart-mrr.svg` | MRR for the same five rows | same |
| `benchmark-chart-latency.svg` | p50 / p95 per stage inside Lambda | "M4 latency per stage" |
| `workflow-benchmark.svg` | Precision, recall, false-suggestion rate and support accuracy, before and after the fragment rule | "Workflow Learning Lite, M5" |
| `aws-architecture-poster.svg` | Nine services with their job and reason, five measured stats, the cost guardrails | the headline table, plus AWS Cost Explorer (below) |

Each SVG draws its own dark card in the `docs/DESIGN.md` colours, so it reads the same on GitHub's
light and dark themes.

**The cost figure.** `$1.86` is AWS Cost Explorer usage before credits for 17-19 September 2026,
queried on 19 September:

```bash
aws ce get-cost-and-usage --region us-east-1 --time-period Start=2026-09-17,End=2026-09-20 --granularity MONTHLY --metrics UnblendedCost --filter "{\"Dimensions\":{\"Key\":\"RECORD_TYPE\",\"Values\":[\"Usage\"]}}" --group-by Type=DIMENSION,Key=SERVICE
```

The breakdown was OpenSearch $1.75, Amplify $0.10, and every other service under $0.01. Cost Explorer
lags by up to a day, so the figure only grows until teardown.
