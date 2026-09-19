# CROWN-X milestones

Each milestone: goal · scope · out of scope · done-means (each with its verification level) · kill
criteria · stage prompt. This file is the contract; the stage prompt in `prompts/` is the detailed brief.
Run with `/milestone <id>`, which loads the prompt; verify with `/verify-stage <id>`. Levels:
`unit` = tests with doubles, `integration` = real service, `live` = deployed URL in a browser.

---

## M0 · Preparation (before opening, no project code)
**Goal:** start at opening with nothing to set up.
**Scope:**
- AWS account with credits and a budget alert
- Builder Center student verification
- region chosen, Bedrock model access checked in it
- local tools: Python 3.12, uv, Node 22, pnpm, AWS CLI, SAM CLI, Docker, Git
- Claude Code updated
- read `docs/`

**Out of scope:** any application code, repository, or generated demo data (write the demo scenario as
a spec only).

**Done means:**
- [ ] `aws sts get-caller-identity` works (integration)
- [ ] Bedrock model list includes the chosen answer and embedding models in the region (integration)
- [ ] `sam --version`, `docker --version`, `pnpm --version` and `uv --version` work (integration)
- [ ] Opening-hour steps in README rehearsed on paper

**Stage prompt:** `prompts/00-OPENING-BOOTSTRAP.md` closes M0 at the event opening.

---

## M1 · Walking skeleton, deployed (Thursday)
**Goal:** the thinnest path from browser to AWS and back, deployed.
**Scope:**
- fresh public repo with this kit at its root
- `python scripts/install_ui_skills.py`
- web app shell (Next.js, Tailwind v4, shadcn init, DESIGN.md tokens, Geist, Phosphor)
- SAM stack: HTTP API, `/health`, S3 bucket with pre-signed upload, ingestion Lambda for TXT and MD
  (PDF may come in M2), OpenSearch index, DynamoDB table
- `/query` returning top-k chunks with IDs (no model yet, or one simple Bedrock call)
- deploy API and web
- fill in the commands in CLAUDE.md; run `/run-skill-generator`
- `/aws-ship check`, including the retrieval-store ADR and a measured Bedrock call

**Out of scope:** conflicts, timeline, UI polish, auth, PDF edge cases.
**Done means:**
- [ ] Health check green on the deployed API (live)
- [ ] Upload one Markdown file through the deployed web app; the document reaches `Ready` (live)
- [ ] Ask a question and see chunk IDs that resolve to the uploaded file (live)
- [ ] Workspace filter present in the OpenSearch query; cross-workspace test passes (unit + integration)
- [ ] CI runs lint, typecheck and tests on push; gitleaks passes (integration)
- [ ] CLAUDE.md commands filled in and working

**Kill criteria:** deployment isn't working by Thursday evening → switch to the Build It fallback
(SAM Local + OpenSearch in Docker) for M2-M3 and retry Ship It on Saturday morning; record an ADR.

**Stage prompt:** `prompts/01-M1-WALKING-SKELETON.md`

---

## M2 · Grounded answers + eval baseline (Thursday night to Friday)
**Goal:** answers that cite validated evidence, and an honest no-evidence path.
**Scope:**
- PDF extraction with the empty-extraction error
- hybrid retrieval
- query in two calls, retrieval then answer (ADR-009)
- Bedrock answer call with delimited evidence and structured output
- citation validation against the retrieved set
- statuses `grounded`, `partial` and `insufficient_evidence`
- audit events
- golden dataset v1 (lookup, synthesis, no-answer, distractor, injection, cross-workspace cases)
- eval runner; baseline recorded in `docs/BENCHMARKS.md`

**Out of scope:** contradictions, timeline.

**Done means** (split into two independent gates on 2026-09-18, ADR-016):

*M2 Offline Gate* (no Bedrock needed; GREEN 2026-09-18, see `docs/CHECKLIST.md`):
- [x] PDF extraction by page, with the empty-text and unreadable-PDF failures (unit)
- [x] Chunking and deterministic metadata (`version_label`, `source_timestamp`) on every demo file (unit)
- [x] Stored evidence snapshot; `/answer` loads it and never retrieves again (unit)
- [x] Citation contract: an invented evidence ID is dropped (unit)
- [x] Evidence escaping: a document can't close or forge an `<evidence>` block (unit)
- [x] Workspace isolation, including a cross-workspace `query_id` returning 404 (unit, and live for the 404)
- [x] No-evidence question: zero model calls, `insufficient_evidence` (unit + offline eval)
- [x] Provider abstraction: MockProvider and BedrockProvider switch by configuration only; production
      refuses the mock (unit)
- [x] Evaluation runner and offline baseline recorded with commit and dataset version (offline)
- [x] All tests, lint, typecheck and builds green; redeployed with production on Bedrock (integration)

*Offline Gate additions after ADR-017 / ADR-018* (2026-09-18, no network):
- [x] Groq reliability layer through the scripted MockGroqTransport, every branch (unit)
- [x] Local ONNX embedder and reranker on generated models, plus the real models when downloaded (unit)
- [x] Retrieval correctness with a real local model: offline eval with e5-small, security gate 1.0 (offline)
- [x] BM25 vs dense vs hybrid vs hybrid + rerank measured on v1 and the paraphrase set (offline)
- [x] Workflow events, deterministic miner and read-only suggestions; synthetic benchmark (unit, offline)
- [x] Provider and environment in /health, structured logs, audit records and the banner (unit)
- [x] Tests fail on any outbound connection (socket guard)

*Live Gate* (replaces the External Bedrock Gate, ADR-017; needs the Groq key in SSM and a deploy):
- [x] ONNX embeddings run live; all 7 demo documents reach `ready` on the deployed stack (live, 2026-09-19)
- [x] The golden question answered by Groq with citations to the right passages, over the API (live).
      In the browser on the deployed URL, 2026-09-19: PASS on `https://main.d1jy52bqj8dt1h.amplifyapp.com` (Amplify, M1 S6): banner `production · answers groq · embeddings onnx`, 6 documents ready, the golden question answered by gpt-oss-120b with 3 citations, citation [3] focuses the Sync 5 Decisions passage, the injected line retrieved but neither cited nor repeated, no console or CSP errors
- [x] Live eval: groundedness, recall@8, MRR, latency and fallback rate; gates proposed as ADR-019
- [x] Injection resistance with the real model: 1.0 after the fix (was 0.0 on the first live run)
- [x] Reranker on vs off and gpt-oss-120b vs 20b, measured on the deployed stack
- [x] The demo PDF ingested (`ready`) and cited live (`project-brief-v1.pdf`, Page 1)

**Kill criteria:** hybrid retrieval tuning over 2 hours → ship semantic-only, record it, move on.

**Stage prompt:** `prompts/02-M2-GROUNDED-ANSWERS.md`

---

## M3 · Contradiction engine + conflict inspector (Friday)
**Goal:** the differentiator, working live.
**Scope:**
- claim extraction (rules for dates and numbers; model-assisted normalization for free text)
- the deterministic predicate
- conflict objects and the selection rule
- `/conflicts`
- answer status `conflict`
- conflict inspector UI and evidence panel (crown-ui)
- conflict cases in the golden set

**Out of scope:** timeline, workflow learning, landing page.

**Done means:**
- [ ] Date, numeric and owner conflicts detected; format-only differences aren't conflicts (unit)
- [ ] Selection picks the newer source and names the rule; with no ordering signal it doesn't select (unit)
- [ ] Contradiction precision and recall recorded against the golden set (integration)
- [ ] Seeded deadline conflict shown in the inspector with both passages on the deployed URL (live)
- [ ] Rough demo recording of the path so far

**Kill criteria:** free-text normalization unreliable by Saturday evening → restrict conflict types to
dates and numbers for the demo, and list the rest as a limitation.

**Stage prompt:** `prompts/03-M3-CONTRADICTIONS.md`

---

## M4 · Timeline, polish, reliability (Saturday)
**Goal:** the golden path is judge-ready.
**Scope:**
- timeline API and UI
- every state from docs/UI_UX.md
- the signature motion sequence
- ⌘K Ask palette
- approved Vengeance components adapted
- landing page only if everything else passes
- latency per stage in CloudWatch
- error paths
- limits and throttling
- security acceptance tests automated against the deployed stack
- browser walkthrough with Playwright MCP at 1440 and 1024, keyboard-only, reduced motion

**Out of scope:** new features beyond the golden path.

**Done means:**
- [ ] Timeline shows the value change with the conflict marked (live)
- [ ] ANTI_SLOP.md checklist passes at 1440 and 1024, keyboard-only and with reduced motion (live)
- [ ] A failed request is traceable in CloudWatch by request ID (integration)
- [ ] Security acceptance tests T1-T3, T5-T7 pass (integration)
- [ ] Golden path runs start to finish without a manual rescue step (live)

**Kill criteria:** any polish item threatening the golden path after saturday 23:00 → drop it.

**Stage prompt:** `prompts/04-M4-TIMELINE-POLISH-RELIABILITY.md`

---

## M5 · Workflow Learning Lite (Saturday night, optional)
**Gate:** M4 verified and the golden path live. Otherwise skip to M6.
**Scope:**
- event logging for native actions
- deterministic sequence miner
- suggestion API
- suggestion card and detail view
- save and dismiss
- WL benchmark

**Done means:**
- [ ] Determinism, support and duplicate tests pass (unit)
- [ ] Events → suggestion → save works end to end (integration)
- [ ] Suggestion card explains its events on the deployed URL (live)
- [ ] Golden path still passes with the feature flag on (live)

**Kill criteria:** not live by Sunday 10:00 → disable behind a flag, keep it out of the video.

**Stage prompt:** `prompts/05-M5-WORKFLOW-LEARNING-LITE.md`

---

## M6 · Freeze and submit (Sunday)
**Goal:** submitted early, and correct.
**Scope:** `/release`: the freeze gates, final eval run, README, CREDITS, writeup, video, submission.
Then fixes only.

**Done means:**
- [ ] `/verify-stage M6` all gates pass (live)
- [ ] Video recorded and checked against docs/HACKATHON.md §4
- [ ] Submitted; confirmation recorded in PROGRESS with the time

**Stage prompt:** `prompts/06-M6-FREEZE-AND-SUBMIT.md`

---

## Inserts
- `prompts/07-UI-SCREEN-PASS.md`: one screen, every state, verified in the browser. Used inside M2-M5.
- `prompts/08-TRIAGE-BEHIND-SCHEDULE.md`: when a gate fails or the clock slips, including the Build It fallback.
