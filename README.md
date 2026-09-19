<div align="center">

<img src="docs/media/banner.svg" alt="CROWN-X: ask your project documents a question, and see where they disagree" width="100%">

# 👑 CROWN-X

**Evidence-first answers over evolving project documents: every sentence cites its passage, and
when sources disagree, you see both, which one is current, and the rule that decided it.**

[![Live app](https://img.shields.io/badge/live-Amplify-6e9bff?style=flat-square&logo=awsamplify&logoColor=white)](https://main.d1jy52bqj8dt1h.amplifyapp.com/)
[![CI](https://github.com/theShivansh/CROWN-X/actions/workflows/ci.yml/badge.svg)](https://github.com/theShivansh/CROWN-X/actions/workflows/ci.yml)
[![AWS](https://img.shields.io/badge/AWS-Lambda%20·%20API%20Gateway%20·%20S3%20·%20DynamoDB-FF9900?style=flat-square&logo=amazonwebservices&logoColor=white)](#-aws-architecture--cost)
[![OpenSearch](https://img.shields.io/badge/OpenSearch-BM25%20%2B%20k--NN-005EB8?style=flat-square&logo=opensearch&logoColor=white)](#-ai-pipeline-deep-dive)
[![Groq](https://img.shields.io/badge/Groq-gpt--oss--120b-F55036?style=flat-square)](#-ai-pipeline-deep-dive)
[![ONNX](https://img.shields.io/badge/ONNX-bge--small%20in%20Lambda-005CED?style=flat-square&logo=onnx&logoColor=white)](#-ai-pipeline-deep-dive)
<br>
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](services/api)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?style=flat-square&logo=typescript&logoColor=white)](apps/web)
[![Next.js](https://img.shields.io/badge/Next.js-App%20Router-000000?style=flat-square&logo=nextdotjs&logoColor=white)](apps/web)
[![License: MIT](https://img.shields.io/badge/license-MIT-3dd68c?style=flat-square)](LICENSE)

**[Open the live app](https://main.d1jy52bqj8dt1h.amplifyapp.com/)** ·
**[Demo workspace](https://main.d1jy52bqj8dt1h.amplifyapp.com/app/?ws=ws_KFdHFNj0IPUoOs4pQDcMUQ)** ·
[Writeup](docs/WRITEUP.md) · [Benchmarks](docs/BENCHMARKS.md) · [Decisions](docs/DECISIONS.md)

AWS First Commit 2026 · Ship It track · built solo, 17-20 September 2026

</div>

---

## 🎬 See it in action

<p align="center">
  <img src="docs/media/demo-hero.gif" alt="Recorded on the deployed app: Ctrl+K, ask 'What is the current submission deadline?', the answer arrives with citations and 'Sources disagree', a citation opens its passage, the conflict inspector explains the flag, the timeline shows 20 Sep to 22 Sep, and the workflow detail shows the repeated routine" width="100%">
</p>

<p align="center"><sub><b>Ask → cited answer → conflict detected → why it was flagged → value timeline → learned workflow</b>, in about 25 seconds.<br>
Recorded with Playwright on the <a href="https://main.d1jy52bqj8dt1h.amplifyapp.com/">deployed app</a>: real Groq answer, real OpenSearch retrieval, nothing mocked.</sub></p>

<table>
  <tr>
    <td width="50%"><a href="docs/media/conflict-inspector.png"><img src="docs/media/conflict-inspector.png" alt="Conflict inspector: brief v1 says 20 September, organiser update 3 says 22 September and is marked newer"></a><br><b>Conflict inspector:</b> both sources side by side, the newer one marked, and the rule that chose the current value.</td>
    <td width="50%"><a href="docs/media/timeline-view.png"><img src="docs/media/timeline-view.png" alt="Value timeline: 20 Sep 2026 in brief v1, changed to 22 Sep 2026 in organiser update 3, confirmed in meeting notes as the current value"></a><br><b>Timeline:</b> how the deadline changed across every source, with the conflict segment dashed.</td>
  </tr>
  <tr>
    <td width="50%"><a href="docs/media/workflow-learning-card.png"><img src="docs/media/workflow-learning-card.png" alt="Workflow card: Answer Review Workflow, 6 steps, seen 3 times, Save workflow and Dismiss buttons" height="330"></a><br><b>Workflow learning:</b> a repeated 6-step routine, counted by code and named by the model.</td>
    <td width="50%"><a href="docs/media/evidence-chat.png"><img src="docs/media/evidence-chat.png" alt="Answer card: Sources disagree, current value 22 Sep 2026 by newest source date, each sentence with citation chips"></a><br><b>Evidence chat:</b> "Sources disagree" comes from code; every sentence carries citation chips.</td>
  </tr>
</table>

### ⚡ The 30-second demo
1. **Upload** Markdown, text or PDF files: a brief, an organiser email, meeting notes. Or open the
   [demo workspace](https://main.d1jy52bqj8dt1h.amplifyapp.com/app/?ws=ws_KFdHFNj0IPUoOs4pQDcMUQ),
   which already has six documents indexed.
2. **Ask.** Press <kbd>Ctrl</kbd>+<kbd>K</kbd> and type *"What is the current submission deadline?"*
3. **Watch CROWN-X explain.** The answer cites its passages and says the sources disagree (20 Sep
   against 22 Sep). It also names which value is current and why. Open the inspector and the timeline,
   then the **Workflows** card, where CROWN-X has learned a routine the team repeats.

---

## 🧭 Why CROWN-X exists
Project facts change across versions. The brief says submissions close on **20 September**. The
organiser's email moves it to **22 September**. The meeting notes confirm 22. A normal document
chatbot answers from whichever passage it happens to retrieve, and never says that another source
disagrees. Teams find out when it's too late.

| | Typical RAG chatbot | CROWN-X |
|---|---|---|
| Where the answer comes from | whichever passage ranked first | every sentence cites a stored passage, and code drops any that doesn't |
| Sources that disagree | silently picks one | shows both, the current value, and the rule that chose it |
| Who decides it's a conflict | the model, if anyone | **deterministic code**: same fact, same type, different documents, different normalized values |
| "22 Sept" and "2026-09-22" | may be called a conflict | normalized as equal and never flagged (measured: 0 false flags) |
| Nothing relevant found | a confident guess | "Not enough evidence", with **no model call** |
| Text in a document that says "ignore previous instructions" | may be followed | treated as data: it can't change instructions, and a claim supported only by it is dropped |
| Change over time | not modelled | a value timeline ordered by each document's own date |

## ✨ Features

<table>
  <tr>
    <td width="33%" valign="top"><img src="docs/media/evidence-chat.png" alt="Evidence chat"><br><b>💬 Evidence chat</b><br>Answers from <code>gpt-oss-120b</code> over exactly the retrieved passages. A citation validator removes any sentence that cites nothing or cites a passage that wasn't retrieved.</td>
    <td width="33%" valign="top"><img src="docs/media/conflict-inspector.png" alt="Conflict inspector"><br><b>⚖️ Conflict inspector</b><br>Both values with their sources, dates and quoted spans, the newer one marked, and "Why was this flagged?" in plain words.</td>
    <td width="33%" valign="top"><img src="docs/media/timeline-view.png" alt="Timeline"><br><b>🕰️ Timeline reconstruction</b><br>Every value a fact took, oldest first, ordered by the document's own header date. The conflict segment and the current value are marked.</td>
  </tr>
  <tr>
    <td valign="top"><img src="docs/media/workflow-detail-dialog.png" alt="Workflow detail"><br><b>🔁 Workflow Learning Lite</b><br>Detects repeated step sequences in the workspace and shows the exact events behind each one. You can save or dismiss it, and nothing ever runs automatically.</td>
    <td valign="top"><img src="docs/media/benchmark-chart-recall.svg" alt="Retrieval recall chart"><br><b>🔎 Hybrid retrieval</b><br>BM25 plus k-NN in one OpenSearch index, workspace-filtered inside the query and fused by reciprocal rank fusion. Recall@8 is 0.95 on the deployed stack.</td>
    <td valign="top"><img src="docs/media/error-request-id.png" alt="Error card with request ID"><br><b>🧾 Audit trail and request IDs</b><br>Every answer writes an audit record: the evidence IDs, provider, model and outcome. Every error shows a request ID that CloudWatch finds in seconds.</td>
  </tr>
</table>

## 🚶 Product walkthrough

<details open>
<summary><b>Step 1: Upload and ingest</b></summary>
<br>
<img src="docs/media/upload-flow.png" alt="Documents rail: Upload files dropzone, six documents ready with passage and conflict counts" align="right" width="210">

Drop files on the rail. They go **straight from the browser to S3** through a size-limited
pre-signed POST, so no file bytes pass through Lambda. The ingestion Lambda then:
- parses the file;
- splits it into passages with character offsets;
- embeds each passage locally with ONNX;
- indexes each passage in OpenSearch;
- extracts typed claims by rule.

Each document then shows how many passages it has and how many conflicts involve it.

Measured on the deployed stack, a document takes 927 ms p50 and 1367 ms p95 from upload to "Ready".
<br clear="right">
</details>

<details open>
<summary><b>Step 2: Ask, and get a cited answer</b></summary>
<br>
<img src="docs/media/hero-dashboard.png" alt="Full workspace: documents, the cited answer with Sources disagree, the conflict card and the evidence panel">

<kbd>Ctrl</kbd>+<kbd>K</kbd> opens **Ask CROWN**. A question is two calls:
1. `POST /query` retrieves the passages and stores them. The conflict check runs in code before the
   model writes a word.
2. `POST /answer` has the model write over exactly those passages.

The evidence panel lists the 8 passages in rank order, and a citation chip scrolls to its passage.
</details>

<details>
<summary><b>Step 3: Inspect the conflict</b></summary>
<br>
<img src="docs/media/conflict-inspector.png" alt="Conflict inspector">

"Sources disagree" isn't the model's opinion. Code found two claims that share a fact key and a
type, come from different documents, and hold different normalized values. The current value is
chosen by the first written rule that applies:
1. the newest source date;
2. version order;
3. the latest upload, the weakest rule, and named as such.
</details>

<details>
<summary><b>Step 4: See how the value changed</b></summary>
<br>
<img src="docs/media/timeline-view.png" alt="Timeline">

Every source's value, oldest first, with changes and conflicts marked. Arrow keys step through the
sources, and each stop carries a full accessible label.
</details>

<details>
<summary><b>Step 5: Let CROWN-X learn the routine</b></summary>
<br>
<img src="docs/media/workflow-detail-dialog.png" alt="Workflow detail dialog with three matched occurrences">

After the team ran *ask → read → inspect conflict → open timeline → open passage → copy answer*
three times, the miner suggested it as a workflow. The card reads "Finished 3 of the 12 times it
started with 'ask a question'", never a bare percentage. The detail view lists the exact events
that matched.
</details>

---

## 🏗️ Architecture

<img src="docs/media/architecture-overview.svg" alt="Architecture: browser on Amplify, API Gateway, two Lambdas, S3, OpenSearch, DynamoDB, Groq, CloudWatch" width="100%">

```mermaid
flowchart LR
    U["Browser<br/>Next.js static export<br/>Amplify Hosting"] -->|HTTPS| G["API Gateway<br/>HTTP API · CORS · throttles"]
    U -->|"pre-signed POST ≤ 5 MB"| S3[("S3<br/>documents · model files")]
    G --> L["Lambda: API<br/>Python 3.12 · ONNX embeddings<br/>quota · citation validator"]
    L -->|async invoke| I["Lambda: ingestion<br/>parse · chunk · embed · claims"]
    I --> S3
    L --> OS[("OpenSearch<br/>BM25 + k-NN")]
    I --> OS
    L --> D[("DynamoDB<br/>claims · audit · events · quotas")]
    I --> D
    L -->|"key from SSM"| Q["Groq<br/>gpt-oss-120b"]
    L -.-> CW["CloudWatch Logs<br/>request_id · stage_ms"]
    I -.-> CW
```

<details>
<summary><b>One question, end to end (sequence diagram)</b></summary>

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant A as Lambda API
    participant Dy as DynamoDB
    participant O as OpenSearch
    participant G as Groq
    B->>A: POST /workspaces/{ws}/query
    A->>Dy: ADD QUOTA#questions#hour (429 before any work if over)
    A->>A: embed question (ONNX bge-small, ~4 ms)
    A->>O: BM25 and k-NN, workspace filter inside each query
    A->>A: RRF fusion → top 8 → conflict compare (code)
    A->>Dy: store query + evidence
    A-->>B: evidence, conflicts (the UI renders them now)
    B->>A: POST /workspaces/{ws}/answer {query_id}
    A->>Dy: ADD QUOTA#answers#hour
    A->>G: passages as an escaped data block (one call)
    G-->>A: AnswerDraft (structured)
    A->>A: finalize(): drop uncited claims, status by code
    A->>Dy: audit record (evidence IDs, model, outcome)
    A-->>B: answer + citations + status
```
</details>

## 🧠 AI pipeline deep dive

<img src="docs/media/retrieval-pipeline.svg" alt="Evidence pipeline: ingest, retrieve, answer" width="100%">

| Stage | What happens | Where in the code |
|---|---|---|
| **Parsing** | Markdown, text and PDF (pypdf). The text is normalized before chunking. | [`adapters/pdf.py`](services/api/src/crownx/adapters/pdf.py), [`domain/chunking.py`](services/api/src/crownx/domain/chunking.py) |
| **Chunking** | Section-aware chunks of about 1,000 characters with a 120-character overlap at word boundaries. Each passage keeps its character offsets, so a citation opens the exact span. | [`domain/chunking.py`](services/api/src/crownx/domain/chunking.py) |
| **Metadata extraction** | The version label and source date come from the document header only (at most five lines). A date quoted in the body is never taken for the document's date, and an ambiguous date gives none. | [`domain/metadata.py`](services/api/src/crownx/domain/metadata.py) |
| **ONNX embeddings** | `bge-small-en-v1.5` int8, run by onnxruntime **inside the Lambda**. It takes 4 ms p50 per question, with no model API call and no per-call cost. | [`adapters/onnx_models.py`](services/api/src/crownx/adapters/onnx_models.py) |
| **Hybrid retrieval** | BM25 and k-NN (HNSW) in one OpenSearch index, with `workspace_id` filtered **inside** each query, so isolation is enforced before anything reaches a model. | [`adapters/opensearch.py`](services/api/src/crownx/adapters/opensearch.py) |
| **RRF** | Reciprocal rank fusion, k = 60, then near-duplicate removal and the top 8. | [`domain/fusion.py`](services/api/src/crownx/domain/fusion.py) |
| **Cross-encoder reranking** | `ms-marco-MiniLM-L-6-v2` int8 is built and benchmarked, and **off in production**. It lifts MRR from 0.694 to 0.864 but adds more than the +150 ms p95 gate, and recall@8 doesn't change (ADR-017). | [`adapters/onnx_models.py`](services/api/src/crownx/adapters/onnx_models.py) |
| **AnswerDraft** | The model returns a structured `AnswerDraft` (answer, claims with evidence IDs, an insufficient flag), with extra fields forbidden. The passages are sent as an escaped data block, never as instructions. | [`domain/answering.py`](services/api/src/crownx/domain/answering.py), [`adapters/groq.py`](services/api/src/crownx/adapters/groq.py) |
| **Citation validator** | `finalize()` keeps only claims whose citations all point to retrieved passages. It drops any claim supported only by text addressed to an assistant, and sets the status in code. | [`domain/answering.py`](services/api/src/crownx/domain/answering.py), [`domain/injection.py`](services/api/src/crownx/domain/injection.py) |
| **Conflict engine** | Rule-based claim extraction (a trigger phrase plus a date, number or owner), normalization, the deterministic predicate, and the selection rules. | [`domain/claims.py`](services/api/src/crownx/domain/claims.py), [`domain/conflicts.py`](services/api/src/crownx/domain/conflicts.py), [`domain/selection.py`](services/api/src/crownx/domain/selection.py) |
| **Workflow miner** | Contiguous step sequences per derived session, with at least 3 distinct steps, a minimum support, and the fragment rule. The output is deterministic. | [`domain/workflow.py`](services/api/src/crownx/domain/workflow.py) |

> [!NOTE]
> **Why Groq and not Bedrock?** On day one, the new AWS account could list Bedrock models, but every
> inference call was denied while AWS verified the account. The answer model therefore sits behind a
> provider interface: Groq in production, with **Bedrock one configuration switch away**
> ([`adapters/bedrock_answer.py`](services/api/src/crownx/adapters/bedrock_answer.py), ADR-013 and
> ADR-017). The fallback is `gpt-oss-20b`, tried once when the primary is rate-limited.

## 🔁 Workflow Learning Engine

```mermaid
flowchart LR
    E["UI + server events<br/>IDs only · UUIDv7<br/>server clock orders all"] --> S["Derived sessions<br/>30-min gap"]
    S --> M["Miner<br/>contiguous sequences<br/>≥ 3 distinct steps<br/>support ≥ min"]
    M --> F["Fragment rule<br/>drop sub-sequences with<br/>no support of their own"]
    F --> N["Groq names it once<br/>(step types + timings only)<br/>rule name if it fails"]
    N --> C["Card: counts, not %<br/>Save → versioned template<br/>Dismiss → stays dismissed"]
```

<table>
  <tr>
    <td width="36%" valign="top"><img src="docs/media/workflow-learning-card.png" alt="Workflow card"></td>
    <td valign="top">

**What code does and what the model does:**
- **Code** records the events, orders them by the server's clock, deduplicates retries by event ID,
  derives the sessions, counts the sequences and computes the support.
- **The model** is shown only the step types and relative timings, and suggests a name like "Answer
  Review Workflow". If the call fails, the card keeps the rule-based name.
- **Nothing runs automatically.** "Save" writes a versioned template (`WFTEMPLATE#{id}#v{n}`).
  "Dismiss" remembers the support it was dismissed at.

<img src="docs/media/workflow-benchmark.svg" alt="Workflow benchmark before and after the fragment rule">

**What went wrong first:** the first run scored precision **0.4**, because fragments of real workflows
outranked the workflows themselves. The fragment rule (ADR-022) brought it to **1.0**, with every
false suggestion reviewed by hand in [BENCHMARKS](docs/BENCHMARKS.md).
</td>
  </tr>
</table>

## ⚖️ Conflict Detection Engine

<img src="docs/media/conflict-inspector.png" alt="Conflict inspector" width="100%">

```mermaid
flowchart LR
    T["Sentence with a trigger<br/>'submissions close on 20 September 2026'"] --> X["Typed claim<br/>fact=submission_deadline<br/>type=date · value=2026-09-20"]
    X --> P{"Predicate (code)<br/>same fact · same type · both normalized<br/>same unit · different documents · different values"}
    P -- no --> OK["no conflict<br/>'22 Sept' = '2026-09-22'"]
    P -- yes --> SEL["Selection rule, first that applies<br/>1 newest source date → 2 version order<br/>→ 3 latest upload (weakest) → 4 none"]
    SEL --> UI["Answer card · Inspector · Timeline<br/>all rendered from this data, never the model's text"]
```

<img src="docs/media/timeline-view.png" alt="Timeline" width="100%">

**Scoped to the question (ADR-020).** The first version attached a conflict whenever a conflicting
passage was retrieved, and status accuracy fell from 0.825 to 0.275. A conflict card now also needs
the question to name the fact. So a conflict can be missed, but one is never invented.

---

## 📊 Benchmarks (measured only)

> [!IMPORTANT]
> Every number here is copied from [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md), where each one has its
> command, dataset, commit and date. "Live" means the deployed stack with the real providers. The
> charts are generated from those tables by [`scripts/readme_media.py`](scripts/readme_media.py). The
> datasets were written by us, so they show that the system does what it claims on known cases, not
> accuracy on anyone else's documents.

**Headline (final evaluation at the freeze, tag `freeze-1`)**

| What | Result | Where |
|---|---:|---|
| Contradiction precision / recall (6 conflicting pairs, 4 facts) | **1.0 / 1.0** | offline and live |
| Current value and rule chosen correctly | **4 of 4** | offline and live |
| Format-only differences flagged as conflicts | **0** | offline and live |
| Security gate: citation validity, isolation, injection, no model call without evidence | **1.0 each** | offline and live |
| Golden set (40 questions): case pass rate / answer value match | **0.95 / 1.0** | live |
| Conflict questions answered with status `conflict` | **7 of 7** | live |
| Workflow miner precision / recall (20 synthetic scenarios) | **1.0 / 1.0** | offline |

<img src="docs/media/benchmark-chart-recall.svg" alt="Recall@5 and recall@8 on retrieval benchmark v2" width="100%">
<img src="docs/media/benchmark-chart-mrr.svg" alt="MRR on retrieval benchmark v2" width="100%">

**Retrieval benchmark v2** (60 passages, 30 queries: original, paraphrased, Hinglish, indirect, hard
negatives; bge-small for dense)

| System | Recall@5 | Recall@8 | MRR | p50 / p95 | Where |
|---|---:|---:|---:|---:|---|
| BM25 only | 0.700 | 0.783 | 0.632 | 5 / 6 ms | offline, laptop |
| Dense only | 0.867 | 0.883 | 0.839 | 13 / 17 ms | offline, laptop |
| **Hybrid RRF (production)** | 0.883 | **0.967** | 0.694 | 21 / 24 ms | offline, laptop |
| Hybrid + rerank (off) | 0.950 | 0.967 | 0.864 | 147 / 183 ms | offline, laptop |
| **Hybrid RRF, deployed** | **0.917** | **0.950** | **0.747** | 242 / 1191 ms (client, network included) | live |

Recall@8 is the number that limits answers, because the model reads all 8 passages. Equal-weight RRF
costs MRR, and weighted fusion is parked until it can be tuned on a separate development set.

<img src="docs/media/benchmark-chart-latency.svg" alt="Latency per stage inside Lambda" width="100%">

<details>
<summary><b>Offline against live, and every run, including the weak ones</b></summary>

| Run | Where | Pass rate | Value match | Groundedness | Fallback rate |
|---|---|---:|---:|---:|---:|
| Offline gate (scripted answers, pipeline properties only) | laptop | 0.55 | not model quality | n/a | n/a |
| Live run 4, paced at 2.5 s | deployed | 0.90 | 0.929 | 0.929 | **0.45** (Groq rate limits) |
| Live run 5, paced at 12 s (headline) | deployed | **0.95** | **1.0** | **0.964** | 0 |

Offline and live are never averaged together. The first live retrieval run at the freeze silently
lost 19 of 63 queries to our own rate limits. Its numbers were thrown away, the harness was fixed to
fail on any error, and the clean rerun is the one reported. The full story is in BENCHMARKS.
</details>

## 🛡️ Security and reliability

| Concern | What CROWN-X does | Proof |
|---|---|---|
| **Prompt injection** | Retrieved text is sent as an escaped data block. A claim supported only by text addressed to an assistant is dropped by code, whatever the model did. | injection cases at 1.0, offline and live; SECURITY T1 |
| **Citation whitelist** | `finalize()` accepts only evidence IDs that were retrieved for this query and stored with it. | citation validity 1.0 |
| **Workspace isolation** | The `workspace_id` filter sits inside every OpenSearch query and every DynamoDB key, before any result reaches a model. | isolation cases at 1.0; cross-workspace acceptance test against the deployed stack |
| **No evidence, no model call** | An empty result returns `insufficient_evidence` without calling Groq. | zero-model-call cases at 1.0 |
| **Retry and fallback** | A timeout, or a 429 asking to wait 2 s or less, is retried once. Otherwise the answer falls back once to `gpt-oss-20b`, and every attempt is recorded. A timeout gives a clear error with its request ID. | recorded 504 in the Playwright `@critical` tests |
| **Cost bounds** | Per-route throttles (`/answer` 1 rps), and 60 questions per workspace per hour counted with DynamoDB `ADD` **before** any work. | T7: the 61st question is a 429, and its log shows no stage ran |
| **Audit trail** | Each answer writes `AUDIT#{ts}#{request_id}`: evidence IDs, provider, model, the model that actually answered, and the outcome. | [`app/service.py`](services/api/src/crownx/app/service.py) |
| **Observability** | Every log line carries `request_id`, route, status, error code and `stage_ms`. The UI shows the request ID on every error. | the diagnosis drill: an ID from the UI is found in Logs Insights |
| **Secrets** | The Groq key is an SSM SecureString, read at cold start. `.env` is denied to tools, and gitleaks runs in CI. | CI "Secret scan" job |

Threat model and acceptance tests: [`docs/SECURITY.md`](docs/SECURITY.md).

## ☁️ AWS architecture and cost

<img src="docs/media/aws-architecture-poster.svg" alt="AWS architecture poster: nine services, measured stats, cost guardrails" width="100%">

| AWS service | Job in CROWN-X | Why this service |
|---|---|---|
| **Amplify Hosting** | Serves the static Next.js export, and rebuilds on every push | Git-connected deploys with no server to run (ADR-014) |
| **API Gateway (HTTP API)** | CORS for the app's origin; throttles per route | A managed edge, cheap per request; the throttles are a cost control (ADR-021) |
| **Lambda** (arm64, 2 GB) | The API and the ingestion worker, one least-privilege IAM role each; ONNX runs inside | Scales to zero; local embeddings add no per-call cost (ADR-017) |
| **S3** | Browser uploads via a size-limited pre-signed POST, plus the pinned model files | No file bytes pass through Lambda, and S3 enforces the size |
| **OpenSearch Service** | BM25 and k-NN in one index, one `m7g.medium` node | Hybrid retrieval with metadata filters in one store (ADR-011) |
| **DynamoDB** (on demand) | Workspaces, documents, claims, queries, audit, events, templates, quota counters (TTL) | Everything is keyed by workspace |
| **CloudWatch Logs and Logs Insights** | Structured logs with `request_id` and per-stage latency | Any error on screen can be traced in seconds |
| **SSM Parameter Store** | The Groq key as a SecureString | The key never enters the repo, the template or the logs |
| **IAM and CloudFormation (SAM)** | One role per function; the whole backend is one template | Reviewable least privilege, and repeatable deploys |

**Measured cost.** AWS Cost Explorer, usage before credits, 17-19 September 2026, as reported on 19
September:

| Service | USD |
|---|---:|
| OpenSearch Service (one node, running all the time) | 1.75 |
| Amplify | 0.10 |
| DynamoDB, S3, API Gateway, Bedrock (day-one smoke tests) | < 0.01 each |
| Lambda, CloudWatch | 0.00 (free tier) |
| **Total** | **1.86**, all covered by credits |

Groq is billed outside AWS and isn't included. The priced alternative for OpenSearch Serverless was
at least five times the cost (ADR-011). Everything is torn down after judging.

## 🗂️ Folder structure

```text
CROWN-X/
├── apps/web/                    Next.js App Router · TypeScript strict · Tailwind v4 · static export
│   ├── app/                     routes: / (start) and /app (workspace)
│   ├── components/workspace/    answer card, evidence panel, conflict inspector, value timeline,
│   │                            Ask palette, workflow card and detail
│   ├── lib/                     typed API client (Zod), timeline/conflict/workflow view logic + tests
│   └── e2e/                     Playwright @critical tests with recorded API fixtures
├── services/api/src/crownx/
│   ├── domain/                  pure logic, no AWS: chunking, metadata, claims, conflicts,
│   │                            selection, timeline, fusion, answering, injection, workflow miner
│   ├── adapters/                OpenSearch, DynamoDB, S3, Groq, Bedrock, ONNX, PDF
│   └── app/                     Lambda handlers, service layer, ingestion, workflow API
├── infra/template.yaml          the whole backend as one AWS SAM template
├── evals/                       golden sets, retrieval v2 corpus, workflow benchmark, results/
├── demo/                        the demo scenario, its documents, and seed.py
├── scripts/                     model fetch (pinned sha256), README charts, kit validator
└── docs/                        PRD, SRS, architecture, design, 22 ADRs, benchmarks, security,
                                 writeup, progress log, media/
```

## 💻 Local development
You'll need Node 22 with pnpm 10, and Python 3.12 through [uv](https://docs.astral.sh/uv/). Deploying
also needs the AWS CLI and the SAM CLI. These are the exact commands from [`CLAUDE.md`](CLAUDE.md):

```bash
cd services/api && uv sync && uv run pytest -q
```

```bash
cd apps/web && pnpm install --frozen-lockfile && pnpm test && pnpm lint && pnpm typecheck && pnpm build
```

```bash
cd services/api && uv run ruff check src tests
```

```bash
cd services/api && uv run python ../../evals/run.py --offline
```

- **Web app:** `cd apps/web && pnpm dev`, with `NEXT_PUBLIC_API_URL` set to the API.
- **Browser tests:** `pnpm e2e` runs the `@critical` tests against the static build, with recorded API
  responses.
- **Local models:** `python scripts/fetch_models.py` downloads them into `services/api/.models/`, and
  checks each one's sha256.
- **Deploy:** `sam build` and `sam deploy` from `infra/`, with the parameters in
  [`docs/HANDOFF.md`](docs/HANDOFF.md). Then seed the demo with `python demo/seed.py --api <ApiUrl>`.
- **README charts:** `python scripts/readme_media.py` regenerates every SVG in `docs/media/`.

The full stack needs OpenSearch and a Groq key, so there's no complete local run. That's why this is
a Ship It submission.

## 🧪 Evaluation framework

| Gate | Command | What it proves |
|---|---|---|
| **Offline gate** | `uv run python ../../evals/run.py --offline` | The real API handlers with a scripted model transport and a local index. It proves the pipeline properties (citations, isolation, injection, conflicts), never model quality. |
| **Live gate** | `... --api <ApiUrl> --pace 12` | Fresh seeded workspaces on the deployed stack, with real Groq and OpenSearch. The demo workspace isn't touched. |
| **Golden dataset** | [`evals/golden/v1.jsonl`](evals/golden/v1.jsonl) | 47 cases: lookups, synthesis, distractors, injections, cross-workspace, insufficient evidence, and 7 conflict cases |
| **Retrieval v2** | `... --retrieval-only --dataset retrieval-v2` | 60 passages and 30 queries with passage-level labels, frozen before the first run. It fails on any HTTP error. |
| **Workflow benchmark** | `uv run python ../../evals/workflows/run.py` | 20 seeded scenarios with planted workflows, near misses, retries and noise. The output is byte-identical on every run. |
| **Tests** | CI on every push | 343 API tests, 28 web unit tests, 7 Playwright end-to-end tests, lint, typecheck, and a gitleaks secret scan |

## 🖼️ Screenshots gallery
All of these were captured from the deployed app with Playwright: no mockups. How to recapture them:
[`docs/media/README_ASSETS.md`](docs/media/README_ASSETS.md).

| | |
|---|---|
| <img src="docs/media/hero-dashboard.png" alt="Workspace with a cited answer"> | <img src="docs/media/workflow-detail-dialog.png" alt="Workflow detail dialog"> |
| The whole workspace after the golden question | The events behind a learned workflow |
| <img src="docs/media/conflict-inspector.png" alt="Conflict inspector"> | <img src="docs/media/error-request-id.png" alt="Error card with request ID"> |
| The conflict inspector | Every error carries a request ID |

## 🎥 Video demo
> **YouTube link: to be added after recording** (3 minutes or less). It will be recorded from
> [`docs/VIDEO_TAKE_SHEET.md`](docs/VIDEO_TAKE_SHEET.md).

| Time | Segment |
|---|---|
| 0:00 | The problem: facts change across document versions |
| 0:30 | Ask with Ctrl+K; retrieval and the conflict check run before the model writes |
| 0:50 | The cited answer: "Sources disagree", the current value, and the rule |
| 1:10 | The conflict inspector, and why the deterministic predicate flagged it |
| 1:30 | The value timeline |
| 1:45 | Workflow Learning Lite: the routine, why it was detected, the events behind it |
| 2:00 | The architecture on AWS |
| 2:30 | Live diagnosis: a request ID from the UI, found in CloudWatch |
| 2:45 | Measured results, cost bounds, and what I learned |

## 🗺️ Roadmap

| Status | Item |
|---|---|
| ✅ **Shipped** | Cited answers, the deterministic conflict engine, value timelines, Workflow Learning Lite, hybrid retrieval, audit trail, limits and throttles, request-ID tracing, CI with end-to-end tests |
| 🔜 **Next** | Claim extraction for free-text facts, where a model may extract but still never decides a conflict · Cognito accounts and sharing · weighted fusion tuned on a separate development set · Bedrock as the production answer model once the account is verified |
| 🔭 **Future** | Human review of conflicts · a read-only MCP server (`search_documents`, `find_conflicts`, `get_timeline`) · durable orchestration (LangGraph) · permissioned workflow execution · external connectors · OpenTelemetry |

LangGraph is on the roadmap only: the shipped pipeline is plain, deterministic Python.

## 📚 Lessons learned
From the [ADRs](docs/DECISIONS.md) and the Learning log in [PROGRESS](docs/PROGRESS.md):
- **Check model access with one real call on day one.** Listing Bedrock models proved nothing. The
  provider interface built that day is why the product shipped on time (ADR-017).
- **Detecting a conflict and deciding whether it matters to a question are separate problems.**
  Mixing them flagged almost every question (ADR-020).
- **Use one clock.** Ordering events by the browser's clock scrambled workflow sequences. The server
  clock and event-ID deduplication fixed it (ADR-022).
- **A log line in a test isn't a log line in CloudWatch.** The standard INFO logs never arrived; only
  the Powertools logger's lines did.
- **A benchmark that hides its errors is worse than no benchmark.** Our own rate limits silently ate
  19 queries of a live run. The harness now fails on any error.
- **Measure before switching something on.** The reranker improves MRR, and it stays off because it
  misses its latency gate without changing what the model reads.

## 🎯 AI engineering highlights

| Feature | AI engineering skill it shows |
|---|---|
| Citation validator + `AnswerDraft` schema | Structured outputs, grounding, and hallucination control enforced by code, not by the prompt |
| Deterministic conflict predicate | Knowing where an LLM must not decide, and keeping a model out of correctness-critical logic |
| Hybrid BM25 + k-NN + RRF | Retrieval engineering: sparse and dense fusion, metadata filtering, multi-tenant isolation |
| Reranker measured and left off | Latency/quality trade-offs made against a gate set in advance |
| ONNX int8 embeddings in Lambda | Model serving on serverless CPU, with pinned sha256 artifacts and zero per-call cost |
| Retrieval v2 benchmark with Hinglish and hard negatives | Evaluation design: passage-level labels, categories, a frozen test set, no tuning on it |
| Offline and live gates, never averaged | Honest evaluation, separating pipeline properties from model quality |
| Injection defence in data and code | LLM security: untrusted-context handling, with the code backstop tested live |
| Groq primary, fallback model, Bedrock switch | Provider abstraction, resilience, and vendor independence |
| Workflow miner + model naming | Deterministic pattern mining, with the LLM used only where it's safe (naming) |
| Request IDs + per-stage latency | LLM observability: finding any failure on screen in the logs in seconds |
| Quotas before work, throttles per route | Cost engineering for LLM products |

## 🤖 AI tools disclosure
- **Claude Code (Claude Opus 5)** planned, implemented, tested, reviewed and verified every
  milestone. The working method is in `CLAUDE.md` and `.claude/`: skills, hooks, subagents, and plan
  mode for each milestone.
- **GitHub Copilot** gave inline completions in the editor.
- **Groq (`openai/gpt-oss-120b`, falling back to `openai/gpt-oss-20b`)** is a runtime service of the
  product, not a coding tool. It writes answers over retrieved evidence and names detected workflows.

<details>
<summary><b>How this repository works with Claude Code</b></summary>

| Feature | How this repository uses it | Why |
|---|---|---|
| `CLAUDE.md` | Rules that each name what enforces them; the commands; how to work | Loaded every session, so it's kept short |
| Skills | `/milestone`, `/verify-stage`, `/record-decision`, `/aws-ship`; domain skills loaded by description | Detail loads only when it's used |
| Subagents | Four read-mostly specialists: reviewer, security, evals, ui-verifier | Isolate context-heavy review; building stays in the main session |
| Hooks | SessionStart context, PreToolUse guards (secrets, force-push), PostToolUse format, Stop gate | Deterministic enforcement that doesn't rely on memory |
| Permissions | `.env`, keys and force-push are denied; push, deploy and AWS deletes ask first | Safety without a prompt for every routine command |
| Plan mode | Each milestone is planned and approved before building | Scope is agreed before code |
</details>

## 🙏 Credits and license
Models, components, fonts and their licences are listed in [`CREDITS.md`](CREDITS.md):
- the models: BAAI `bge-small-en-v1.5` (MIT), `ms-marco-MiniLM-L-6-v2` (Apache-2.0), OpenAI
  `gpt-oss` (Apache-2.0) served by Groq;
- shadcn/ui (MIT), Motion (MIT), Geist (OFL), Phosphor Icons (MIT);
- AWS Lambda Powertools (MIT), opensearch-py (Apache-2.0), onnxruntime (MIT), pypdf (BSD).

The demo documents and every evaluation dataset were written for this project during the event.
Released under the [MIT License](LICENSE).

---

<div align="center">

<sub>Built with <b>Claude Code (Opus 5)</b>, <b>GitHub Copilot</b>, <b>Groq</b>, and <b>AWS</b> · AWS First Commit 2026 · Mumbai, ap-south-1</sub>

</div>
