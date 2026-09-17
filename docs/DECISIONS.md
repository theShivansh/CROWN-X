# CROWN-X decisions

Newest first. Add entries with `/record-decision` (template in that skill). Past 40 entries, move
superseded ones to `docs/decisions/archive.md` and keep their index lines.

## Index
- ADR-015 · 2026-09-17 · M1's Thursday-evening kill criterion deferred while AWS verifies the account · accepted
- ADR-014 · 2026-09-17 · Web hosting: Amplify Hosting connected to GitHub · proposed
- ADR-013 · 2026-09-17 · Answer and embedding models without Anthropic's use-case form · proposed
- ADR-012 · 2026-09-17 · Region: ap-south-1 (Mumbai) · accepted
- ADR-011 · 2026-09-17 · Retrieval store: a single-node OpenSearch Service domain · accepted
- ADR-010 · 2026-09-16 · Stage prompts and working style written for Opus 5 · accepted
- ADR-009 · 2026-09-16 · A question is two calls: retrieve, then answer · accepted
- ADR-008 · 2026-09-16 · Claude Code harness: one state file, four agents, tested hooks · accepted
- ADR-007 · 2026-09-16 · Third-party UI sources and design skills · accepted
- ADR-006 · 2026-09-16 · Web stack and dark-first design system · accepted
- ADR-005 · 2026-09-16 · Workflow Learning Lite is deterministic and gated behind M4 · accepted
- ADR-004 · 2026-09-16 · Frozen MVP scope with kill criteria · accepted
- ADR-003 · 2026-09-16 · Deterministic contradiction predicate · accepted
- ADR-002 · 2026-09-16 · Evidence-first responses · accepted
- ADR-001 · 2026-09-16 · AWS Ship It first, Build It as fallback · accepted

---

### ADR-015 · 2026-09-17 · M1's Thursday-evening kill criterion deferred while AWS verifies the account
Status: accepted

**Context:** M1's kill criterion switches to the Build It fallback if the deployed path isn't working
by Thursday evening (MILESTONES M1, ADR-001, ADR-004). At 19:13 IST on 2026-09-17 nothing could be
deployed: a Titan V2 `invoke-model` call still returned "Operation not allowed" (B4), and SAM CLI and
Docker weren't installed (B5, B7). The fallback needs Docker too, so it isn't available either. The
user expects AWS to finish verifying the new account within about 24 hours of creation (00:05 IST).
**Decision:** the user waived the Thursday-evening check. `prompts/08-TRIAGE-BEHIND-SCHEDULE.md` is not
run on Thursday; M1 continues with the slices that need no AWS (S4 web, S5 CI) and deploys as soon as
B4, B5 and B7 close.
**Rejected:** running the triage prompt now: its Build It fallback needs Docker, which isn't installed,
so it would not unblock anything tonight.
**Consequences:** M2 and M3 start late if verification slips; the live done-means of M1 are still owed.
**Verify / revisit if:** a Bedrock runtime call succeeds and `sam deploy` works by Friday 12:00 IST.
If not, run the triage prompt then.

### ADR-014 · 2026-09-17 · Web hosting: Amplify Hosting connected to GitHub
Status: proposed (the user chose it at M1 plan approval; accepted when a push deploys the site in S6)

**Context:** The web app is a static export (ARCHITECTURE §8). Judges see the deployed URL and the video,
and a manual release step before every recording is one more thing to forget in a four-day event.
**Decision:** one Amplify Hosting app connected to `github.com/theShivansh/CROWN-X`, branch `main`, with
a monorepo `amplify.yml` (appRoot `apps/web`), `NEXT_PUBLIC_API_URL` as an Amplify environment variable,
and the security headers as `customHeaders`. The user authorizes the GitHub app in the Amplify console.
**Rejected:** manual zip deploys: a release step to remember before each recording. S3 plus CloudFront
by hand: more infrastructure to write for the same static site.
**Consequences:** every push to `main` redeploys the judged URL, so CI has to be green before pushing;
build minutes and hosting draw on the credits.
**Verify / revisit if:** a push in S6 deploys the site and the golden path works on the Amplify URL.

### ADR-013 · 2026-09-17 · Answer and embedding models without Anthropic's use-case form
Status: proposed; the measurement waits until AWS finishes verifying the account (PROGRESS B4)

**Context:** The Anthropic use-case form couldn't be submitted, so Claude Haiku 4.5 is out. The answer
call needs schema-valid output, low latency and a model still served 30+ days after the event. Model
cards and the Price List API (Mumbai, published 2026-09-15), standard tier, USD per 1M tokens:

| Model, ID in ap-south-1 | Access | Structured output on `bedrock-runtime` | Input / output |
|---|---|---|---|
| Qwen3 235B A22B 2507, `qwen.qwen3-235b-a22b-2507-v1:0` | in-Region | tool calling and structured outputs | $0.26 / $1.04 |
| gpt-oss-120b, `openai.gpt-oss-120b-1:0` | in-Region | structured outputs (tool calling not listed) | $0.18 / $0.71 |
| Amazon Nova 2 Lite, `global.amazon.nova-2-lite-v1:0` | global profile only | tool calling (no structured outputs) | not in the Mumbai list |
| Titan Text Embeddings V2, `amazon.titan-embed-text-v2:0` | in-Region | 1,024 dimensions | $0.024 input |

All four are Active, and Bedrock gives at least six months of legacy notice before an end of life. On
2026-09-17 every Converse and InvokeModel call returned "Your account is currently being verified".
**Decision (proposed):** when calls work, run the S0 measurement (one grounded prompt, forced
`submit_answer`, three runs each) and pick the fastest model valid in all runs, preferring in-Region;
Qwen3 235B is the expected pick. Embeddings: Titan V2 at 1,024 dimensions. IDs live only in config.
**Rejected:** Claude Haiku 4.5: needs the form. Smaller models (Nova Micro, Gemma 3, Ministral): cheaper,
but riskier for schema-bound grounded answers (not measured).
**Consequences:** no Anthropic dependency; about $0.001 per grounded question with Qwen3. If gpt-oss wins,
M2 uses structured outputs instead of a forced tool.
**Verify / revisit if:** the measurement is recorded here; revisit if M2's citation precision misses its gate.

### ADR-012 · 2026-09-17 · Region: ap-south-1 (Mumbai)
Status: accepted

**Context:** The team and the demo recording are in India, and every ADR-001 service has to exist in one
Region. Observed from the account on 2026-09-17: the CLI is configured for ap-south-1; Bedrock lists 69
text models there, including in-Region Qwen3 235B and gpt-oss-120b, a `global.` profile for Nova 2 Lite
and on-demand Titan Text Embeddings V2; OpenSearch 3.7 offers m7g.medium.search with encryption at rest.
**Decision:** everything deploys to `ap-south-1`: the SAM stack, Amplify Hosting and the CLI profile;
recorded in `docs/ARCHITECTURE.md` §11.
**Rejected:** us-east-1: the widest model catalogue and the cheapest t3 node, but about 250 ms farther
from the team and the recording, and nothing M1-M3 needs is missing in Mumbai.
**Consequences:** OpenSearch at $0.048 an hour. Models offered only through global profiles need IAM that
names every destination Region.
**Verify / revisit if:** M1's deploy succeeds there; revisit if a required model turns out to be unusable.

### ADR-011 · 2026-09-17 · Retrieval store: a single-node OpenSearch Service domain
Status: accepted 2026-09-18, when the stack deployed: the domain was created and `/health` reports the index `ok`

**Context:** M1 needs BM25 and k-NN in one index, both filtered by `workspace_id`, with deterministic
chunk IDs. AWS Price List API (published 2026-09-11), ap-south-1 / us-east-1, vs $100 credits per team:

| Option | Unit price | 96 hours | Each further 30 days |
|---|---|---:|---:|
| Service: one m7g.medium / t3.small node, 10 GB gp3 | $0.048 / $0.036 per hour | $4.8 / $3.6 | $36 / $27 |
| Serverless classic: 1 OCU dev-test floor | $0.2472 / $0.24 per OCU-hour | $24 / $23 | $178 / $173 |
| Serverless NextGen: compute scales to zero | same per OCU-hour while active | usage-based | storage only |

No account gets free OpenSearch instance hours now (the 12-month offer ended for all pre-2025-07-15
accounts). AWS docs: NextGen `VECTORSEARCH` collections assign their own document IDs, and the first
request after 10 idle minutes waits 10-30 s, against API Gateway's 30 s limit on `/query`.
**Decision:** one domain in `infra/template.yaml`: one data node (m7g.medium.search in ap-south-1,
t3.small.search in us-east-1), 10 GB gp3, one AZ, HTTPS, an access policy naming only the two Lambda
roles. Index `crownx-chunks`: HNSW k-NN with efficient filtering; bulk writes use `refresh=wait_for`.
**Rejected:** NextGen Serverless: server-assigned IDs break idempotent re-indexing, and cold starts land
on the golden path. Classic Serverless: its OCU floor costs at least five times more. Bedrock Knowledge
Bases: too little control over chunk metadata and hybrid scoring.
**Consequences:** idempotent writes by chunk ID, no cold start. Billed while idle (about $1 a day), so
teardown after judging matters; domain creation is slow, so M1 deploys infrastructure first.
**Verify / revisit if:** M1's deploy creates the domain and the cross-workspace test passes against it.
Revisit NextGen Serverless after the event, when idle cost outweighs cold starts.

### ADR-010 · 2026-09-16 · Stage prompts and working style written for Opus 5
Status: accepted

**Context:** Each stage needs a detailed brief that survives context resets. Current guidance for
Claude Opus 5, from Anthropic's prompting material bundled with Claude Code:
- It follows instructions closely, so capital-letter emphasis over-applies.
- It verifies its own work, and explicit "double-check" or "verify with a subagent" instructions cause
  over-verification.
- It delegates to subagents readily, which multiplies cost and time.
- It can widen a task's scope unless the intended scope is stated.
- Claude Code's default effort is already `xhigh`, so a skill setting `effort: high` lowers it.

**Decision:**
- One stage prompt per milestone in `prompts/` (00-06), plus two inserts: the UI screen pass and triage.
- Each prompt gives the goal, context and reasons, the contracts later stages depend on, and
  done-means. Numbered steps appear only where order is fragile.
- Working style lives once in CLAUDE.md: scope, verification in session, a delegation cap, how to
  report.
- The project agents are used when the user asks for an independent pass.
- The reviewer reports every finding with severity and confidence.
- No skill or agent sets `effort`.

**Rejected:**
- Step-by-step scripts for judgment work: they degrade Opus 5's output.
- Mandatory subagent verification at every milestone: over-verification, and doubled time.

**Consequences:** Verification evidence comes from the main session's own runs. Independent passes
remain available on request.
**Verify / revisit if:** A milestone closes with an unverified done-means item, or sessions show scope
drift. Then add the missing context to the prompt, not emphasis.

### ADR-009 · 2026-09-16 · A question is two calls: retrieve, then answer
Status: accepted

**Context:** API Gateway HTTP APIs can't stream a Lambda response and time out after 30 seconds. The UI
must show real stages, because progress that names real work is a design rule. And the signature motion
sequence is evidence arriving, then the answer settling.
**Decision:** `POST /query` retrieves evidence and relevant conflicts and stores the evidence IDs on a
query record. `POST /queries/{id}/answer` makes the single model call over exactly those IDs. No
evidence means no model call.
**Rejected:**
- One synchronous call: no real stages, and the whole budget sits inside one timeout.
- Lambda response streaming: needs Lambda Web Adapter or a non-Python runtime, which is time the
  event doesn't have.
- WebSockets: more infrastructure for one screen.

**Consequences:** Two round trips per question. Citations can only reference evidence the user already
saw.
**Verify / revisit if:** p95 end-to-end latency in BENCHMARKS is dominated by the extra round trip.

### ADR-008 · 2026-09-16 · Claude Code harness: one state file, four agents, tested hooks
Status: accepted

**Context:** Kits v1-v3 kept `.claude/` and CLAUDE.md inside `09_CLAUDE_CODE/`, where Claude Code
doesn't load them. Two hooks printed reminders to stderr with exit 0, which Claude never sees. Eight
agents (five on Opus) had no tool limits, and eight state files needed updating at every milestone.
**Decision:** Kit at the repository root. CLAUDE.md under 120 lines, with each rule naming its
enforcement. One state file (`docs/PROGRESS.md`) plus this log. Four read-mostly agents (reviewer,
security, evals, ui-verifier) with tool limits. Workflows as skills (commands are merged into skills).
Hooks that decide (JSON permission decisions, a Stop gate with exit 2), covered by
`tests/test_hooks.py`. Playwright and AWS documentation MCP in `.mcp.json`.
**Rejected:** architect, backend, frontend and retrieval agents (building belongs in the main session,
where context is shared); CHECKLIST, HANDOFF, BLOCKERS and VERIFICATION files (they drift within a day).
**Consequences:** less ceremony per milestone; the gates are real. Hooks need Python on PATH as `python`.
**Verify / revisit if:** `python scripts/validate_kit.py` and `pytest tests` pass; revisit if a hook
blocks legitimate work twice.

### ADR-007 · 2026-09-16 · Third-party UI sources and design skills
Status: accepted

**Context:** The operator named Vengeance UI, Skiper UI, Animmaster Lib, taste-skill and UI UX Pro
Max. The event rules require a credit and a licence permitting use for anything not written during
the event.
**Decision:**
- **Vengeance UI (MIT):** pinned at `813d9c1`; six components approved, with uses in
  `.claude/skills/crown-ui/references/COMPONENTS.md`.
- **taste-skill** `design-taste-frontend` (MIT): pinned at `ccbc156`.
- **ui-ux-pro-max** (MIT): pinned at `8bd29e7`, installed as project skills by
  `scripts/install_ui_skills.py`.
- **Skiper UI:** conditional only (no public source to audit; attribution required).
- **Animmaster Lib:** not used (a paid bundle with no verifiable licence).

The ui-ux-pro-max design-system output is an input, not the master: it matched the product to an
"FAQ/documentation landing" pattern and proposed the slate + green developer palette. DESIGN.md
overrides both.
**Rejected:** installing from `main` or websites (unpinned); GSAP-based components (a second animation
library); components importing runtime Google Fonts.
**Consequences:** every component is read and adapted before commit; CREDITS.md lists each.
**Verify / revisit if:** CREDITS.md complete at M6; revisit if a pinned component blocks the Next.js
version in use.

### ADR-006 · 2026-09-16 · Web stack and dark-first design system
Status: accepted

**Context:** Best UI is a prize open to both tracks, and the demo is judged from a video. Generic
AI-dashboard styling is the default failure mode.
**Decision:**
- Stack: Next.js App Router, Tailwind v4, shadcn/ui we own, Motion, Geist and Geist Mono, Phosphor
  icons.
- Tokens: neutral near-black surfaces stepped by tone, one blue accent, semantic states each with an
  icon and a label.
- Dials 3/3/6 for the app. A single signature motion sequence.
- Specified in `docs/DESIGN.md`; contrast computed for every token.

**Rejected:** light-first (the evidence UI reads better dark on video, and one theme halves the work);
Inter + slate (default look); a GSAP scroll-driven landing (time and risk with no score).
**Consequences:** no light theme during the event; the dark tokens must hold AA, which they do.
**Verify / revisit if:** the ANTI_SLOP checklist passes in the M4 browser walkthrough.

### ADR-005 · 2026-09-16 · Workflow Learning Lite is deterministic and gated behind M4
Status: accepted

**Context:** Kit v3 listed Workflow Learning Lite as hackathon P0 while its own plan treated it as late
and removable. The rules weight a working product; an LLM-only miner is hard to test in four days.
**Decision:** Deterministic sequence mining over native events; a model only names a detected pattern.
Built in M5 only if M4 is verified by Saturday evening; otherwise disabled and out of the video.
**Rejected:** P0 on day 2 (competes with the contradiction engine); LLM discovery (not reproducible).
**Consequences:** the core demo is protected; the feature may not ship.
**Verify / revisit if:** M4 verified on time.

### ADR-004 · 2026-09-16 · Frozen MVP scope with kill criteria
Status: accepted

**Context:** "One feature that runs beats five that almost do" (judging criteria). Scope creep is the
top risk.
**Decision:** P0 = upload, index, grounded answer, contradiction, evidence, timeline, deployed UI.
Milestones M1-M6 with done-means and kill criteria in `docs/MILESTONES.md`; new ideas go to the
Parking lot.
**Rejected:** MCP, knowledge graph, autonomous workflows during the event.
**Consequences:** some compelling features wait.
**Verify / revisit if:** M3 verified by Friday night.

### ADR-003 · 2026-09-16 · Deterministic contradiction predicate
Status: accepted

**Context:** A false conflict on screen undermines trust faster than a missed one, and a model-judged
conflict can't be tested exactly.
**Decision:** Claims are normalized to `(subject, attribute, value, unit, source, timestamp)`; code
decides conflicts; a model may only propose normalization. The current value is chosen by an explicit
rule that the response names.
**Rejected:** a model deciding conflicts; resolving silently to the newest document.
**Consequences:** fewer conflict types at first (dates and numbers are the most reliable).
**Verify / revisit if:** contradiction precision recorded in BENCHMARKS.md.

### ADR-002 · 2026-09-16 · Evidence-first responses
Status: accepted

**Context:** The differentiator is provenance, and it makes the demo inspectable by judges.
**Decision:** Every claim carries evidence IDs validated against the retrieved set, or the answer says
the evidence is insufficient.
**Rejected:** free-form answers with a sources list appended.
**Consequences:** some answers are shorter or say "not enough evidence".
**Verify / revisit if:** the citation contract test and citation precision gate pass.

### ADR-001 · 2026-09-16 · AWS Ship It first, Build It as fallback
Status: accepted

**Context:** Built on AWS "decides most" of the score; Ship It is the first prize and judges services,
architecture and cost. Both tracks accept submissions.
**Decision:** Amplify, API Gateway, Lambda, S3, OpenSearch, Bedrock, DynamoDB, CloudWatch, deployed
with SAM. If deployment isn't working by Thursday evening, continue on SAM Local and OpenSearch in
Docker (Build It) and retry the deploy on Saturday.
**Rejected:** a container service or non-AWS hosting (weaker AWS story); a long-term platform stack
(Qdrant, LangGraph) during the event.
**Consequences:** some portfolio components move to post-hackathon.
**Verify / revisit if:** the M1 deploy gate.
