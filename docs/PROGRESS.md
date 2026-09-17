# CROWN-X progress

Next session starts here: at the repository root, confirm the harness is live (SessionStart line, `git add -A` denied, Playwright MCP tools present), close B2-B8, then run `/milestone M1` and start at slice S0 of the approved M1 plan below.

The repo overrules this file; memory overrules neither. Update it before every session ends.

**Event clock:** opened 2026-09-17 08:00 IST (02:30 UTC), the countdown target on the schedule page
(read 2026-09-16 23:43 IST; the countdown was gone at 2026-09-17 10:10 IST). Nothing in the repository
predates it.

**Event deadline (record with time zone):** not published yet. At 2026-09-16 23:43, 2026-09-17 07:39
and 2026-09-17 10:10 IST the schedule page said the hours, including "the deadline the clock stops
on", are still being finalised. Re-check the schedule page and record it here.

## Milestones
| ID | Milestone | Status | Verified at | Commit | Notes |
|---|---|---|---|---|---|
| M0 | Preparation | in progress, blocked | none | none | Harness rehearsed in a scratch copy (installer, validator, 39 tests pass); ADR-011 proposed and confirmed by the user; `demo/SCENARIO.md` written; M1 plan approved. AWS CLI, SAM, uv and Docker missing, so no AWS fact is confirmed (B3-B7) |
| M1 | Walking skeleton, deployed | planned, approved 2026-09-17 | none | none | Plan below; starts at S0 once B3-B8 close |
| M2 | Grounded answers + eval baseline | not started | none | none | |
| M3 | Contradictions + conflict inspector | not started | none | none | |
| M4 | Timeline, polish, reliability | not started | none | none | |
| M5 | Workflow Learning Lite (gated) | not started | none | none | Only if M4 is verified by Saturday evening |
| M6 | Freeze and submit | not started | none | none | |

## M0 facts (bootstrap session, 2026-09-16 23:40 to 2026-09-17 08:00 IST)

**Harness, rehearsed in a scratch copy of the kit** (not the repository, which doesn't exist yet):
- the README's `Copy-Item` command copied all 54 files, including `.claude/`, `.github/` and `.mcp.json`;
- `python scripts/install_ui_skills.py` installed `design-taste-frontend` at `ccbc156` and
  `ui-ux-pro-max` at `8bd29e7` (network and git work);
- `python scripts/validate_kit.py`: "Kit valid: 4 agents, 11 skills, hooks wired, no credential
  patterns.";
- `python -m pytest tests -q`: 39 passed.

The harness was not live in that session. Claude Code ran one folder above the kit, outside any git
repository, so no SessionStart line appeared, `git add -A` was not denied by `guard_bash`, and no
Playwright MCP tools loaded. Check all three again at the repository root.

**Tools** (Windows 11):

| Tool | Result | Needed for |
|---|---|---|
| python | 3.11.9 (Microsoft Store build) | hooks and scripts need 3.11+; the Lambda runtime is 3.12, so the API uses a uv-managed 3.12 |
| pytest, ruff | 9.1.1, 0.16.3 | hook tests, Stop gate |
| node, pnpm | v22.19.0, 10.33.0 | web |
| git | 2.50.0.windows.1, user `theshivanshshukla` | commits |
| aws | not installed | every AWS fact (B3) |
| sam | not installed | build and deploy (B5) |
| uv | not installed | API dependencies, Python 3.12, the `aws-docs` MCP server (B6) |
| docker | not installed | `sam local`, the Build It fallback (B7) |
| gh | not installed | optional |

**AWS account:** not confirmed. The AWS CLI isn't installed and the AWS connector in the Claude session
wasn't authenticated, so identity, the root check, Region, account plan, credits and the budget alert
are all unverified (B3, B8).

**Region:** none configured on this machine. The user chose `ap-south-1` (Mumbai) at M1 plan approval:
nearest to the team and the demo recording, Titan Text Embeddings V2 runs in-Region there, and the
smallest suitable OpenSearch node is $0.048 an hour. (`us-east-1` has the widest model catalogue and
the cheapest t3 node, $0.036 an hour.) S0 verifies it and records the ADR.

**Bedrock shortlist.** From the AWS model cards read 2026-09-16, not from this account. Confirm in the
chosen Region with `aws bedrock list-foundation-models --by-output-modality TEXT` and
`aws bedrock list-inference-profiles`; M1 measures both answer models.

| Role | Model | ID to call | Notes |
|---|---|---|---|
| answer, candidate A | Claude Haiku 4.5 | `global.anthropic.claude-haiku-4-5-20251001-v1:0` | Converse tool use. `bedrock-runtime` needs a geo or global profile, and the geo profiles are US, EU, AU and JP, so Mumbai uses the global one. Needs Anthropic's one-time use-case form (B4) |
| answer, candidate B | Amazon Nova 2 Lite | `amazon.nova-2-lite-v1:0`, or `global.amazon.nova-2-lite-v1:0` | client-side tool calling supported, native structured outputs not; no form needed; listed for ap-south-1 (in-Region or global only: the CLI shows which) |
| embeddings | Titan Text Embeddings V2 | `amazon.titan-embed-text-v2:0` | in-Region only; listed for ap-south-1 and us-east-1; 1,024 dimensions by default (512 and 256 optional); throttled by requests per minute |

Model access today: serverless models are enabled on first use; Anthropic models need the one-time
use-case form first (Bedrock console playground, or `PutUseCaseForModelAccess`).

**Retrieval store:** ADR-011, proposed: a single-node OpenSearch Service domain, about $5 for 96 hours
in Mumbai.

## Blockers
| ID | Blocker | Owner | Closes when |
|---|---|---|---|
| B2 | Submission deadline not published | organisers; you re-check the schedule page | the deadline and its time zone are recorded above |
| B3 | AWS CLI v2 not installed, so no AWS fact is confirmed | you | `winget install -e --id Amazon.AWSCLI`; `aws login` as an IAM user (never root); `aws sts get-caller-identity` shows a non-root identity and `aws configure get region` the chosen Region |
| B4 | Anthropic models need the one-time use-case form | you | form submitted in the Bedrock console playground (Claude Haiku 4.5) in the chosen Region; M1's Converse call succeeds |
| B5 | SAM CLI not installed | you | `winget install -e --id Amazon.SAM-CLI`; `sam --version` works |
| B6 | uv not installed; no Python 3.12 | you | `winget install -e --id astral-sh.uv`; `uv --version` works; `uv python install 3.12` |
| B7 | Docker not installed | you | `winget install -e --id Docker.DockerDesktop`; Docker Desktop running; `docker --version` works |
| B8 | Check-in, event credits, account plan and budget alert unconfirmed. A Free-plan account can't redeem promotional credits (AWS Billing docs), so the event code may need the Paid plan | you | checked in on the First Commit page; credit code redeemed; an AWS Budgets alert exists |
| B9 | No GitHub repository; Claude Code not yet run at its root | you, then Claude | you create an empty public repo; Claude clones it, copies the kit in, reruns the checks, commits by path and pushes after you confirm; you start Claude Code at its root with workspace trust accepted and both MCP servers approved |

## Risks
| Risk | Severity | Mitigation |
|---|---|---|
| Scope creep | high | Frozen milestones, kill criteria, Parking lot |
| Deployment eats day 1 | high | M1 deploys first; Build It fallback decided by Thursday evening |
| Tool setup and AWS access eat the first hours | high | B3-B8 closed in parallel with the harness commit; M1 starts with `/aws-ship check` |
| OpenSearch domain creation slows the first deploy | medium | Deploy infrastructure first and write the API while the domain creates (ADR-011) |
| Anthropic model access blocked (form or account plan) | medium | Nova 2 Lite is the second answer candidate and needs no form |
| Local Python 3.11 against the Lambda 3.12 runtime | medium | uv-managed 3.12 for the API; `sam build --use-container` once Docker runs |
| Poor retrieval | high | Golden set from M2, baseline before tuning |
| False conflict on screen | high | Deterministic predicate; format-equivalence tests |
| Stale answer chosen | high | Explicit selection rule with timestamps and versions |
| Prompt injection via documents | high | Delimited evidence, structured output, test cases |
| AWS cost surprise | medium | Budget alert, limits, one model call per question, teardown |
| Demo fails on the day | high | Record a rough demo Friday; freeze Sunday morning |

## M1 plan (approved by the user, 2026-09-17 10:09 IST)
Decisions made at approval, each recorded as an ADR in S0 once verified:
- **Region:** `ap-south-1`.
- **Retrieval store:** ADR-011, a single m7g.medium.search node with 10 GB gp3 (t3.small.search if
  that node isn't offered for the engine version).
- **Web deploy:** Amplify Hosting connected to the GitHub repo; the user authorizes the GitHub app in
  the Amplify console during S6.
- **Models:** measured in S0: Claude Haiku 4.5 through the global profile against Nova 2 Lite for
  answers (used from M2); Titan Text Embeddings V2 for embeddings.
- **Repository:** the user creates it; Claude makes the first commits by path.

The plan, in slices that each end green, committed by path and pushed:
- **S0**, settle and measure: CLI identity and Region, one Converse call per answer candidate with a
  forced `submit_answer` tool, one embedding call, quotas, the node type, the ADRs, `/aws-ship check`.
- **S1**, infrastructure first, because the domain is slow to create: `infra/template.yaml` (HTTP API,
  two least-privilege Lambdas, S3, DynamoDB, the ADR-011 domain, 14-day logs), deployed with stub
  handlers.
- **S2**, the API core against fakes: workspaces, pre-signed upload, checksum-locked `complete`,
  documents, `/health`, and one error envelope carrying `request_id`.
- **S3**, ingestion and retrieval:
  - heading and paragraph chunks with offsets;
  - Titan embeddings;
  - bulk indexing by `{doc}:{ordinal}` with `refresh=wait_for`;
  - an `ensure_index` event invoked after deploy;
  - `/query` with BM25 and k-NN both filtered by `workspace_id`, fused by RRF (k = 60).
- **S4**, the static-export Next.js app: tokens, upload with progress and polling, a question box that
  shows chunk cards, and `amplify.yml` security headers.
- **S5**, the `web` and `api` CI jobs, the `CLAUDE.md` commands and the product README.
- **S6**, go live: connect Amplify, prove the done-means with Playwright MCP, find the request in
  CloudWatch, run `/run-skill-generator` and `/verify-stage M1`.

Kill criterion: if the deployed path isn't working by Thursday evening, run
`prompts/08-TRIAGE-BEHIND-SCHEDULE.md` (Build It fallback).

## Verification log
One line per `/verify-stage` run: `date time | milestone | commit | gates | level | failures`
- none yet

## Learning log
Learning is a judged criterion (docs/HACKATHON.md §1). One line per thing learned during the event,
with the date: what, and where it showed up.
- none yet

## Parking lot
Ideas that don't strengthen the three-minute demo. Revisit after M6.
- Read-only MCP server (`search_documents`, `find_conflicts`, `get_timeline`, `explain_evidence`)
- Human review state for conflicts
- Light theme
