# CROWN-X progress

Next session starts here: M1's stack is deployed to ap-south-1 and `/health` is green live. The only thing left blocking the golden path is B4: every Bedrock call still returns "Operation not allowed" and the on-demand quota reads 0, so ingestion fails at embedding. When B4 clears: re-upload a document and watch it reach `ready`, run `/query` against the deployed API, run S0's model measurement, then S6 (Amplify, tightened CSP, Playwright walkthrough, /verify-stage M1).

The repo overrules this file; memory overrules neither. Update it before every session ends.

**Event clock:** opened 2026-09-17 08:00 IST (02:30 UTC), the countdown target on the schedule page
(read 2026-09-16 23:43 IST; the countdown was gone at 2026-09-17 10:10 IST). Nothing in the repository
predates it.

**Event deadline (record with time zone):** not published yet. At 2026-09-16 23:43, 2026-09-17 07:39,
10:10 and 13:30 IST the schedule page said the hours, including "the deadline the clock stops
on", are still being finalised. Re-check the schedule page and record it here.

## Milestones
| ID | Milestone | Status | Verified at | Commit | Notes |
|---|---|---|---|---|---|
| M0 | Preparation | done except SAM and Docker | none | `75458e2`, `ae14492` | Harness committed and pushed; non-root CLI identity; Region and model catalogue observed; M1 plan approved. Open: SAM CLI (B5), Docker (B7) |
| M1 | Walking skeleton, deployed | in progress: S1 deployed and healthy; S2, S3, S4 done (unit); S5 done (integration); ingestion blocked at embedding by B4 | live (`/health`, upload to S3, `complete`); unit (S2, S3, S4); integration (S5 CI, deploy) | see git log | Region ADR accepted; models ADR proposed (measurement blocked by B4). S2: `services/api` on Python 3.12 with uv; workspaces, pre-signed upload, checksum-locked `complete`, documents, `/health`, one error envelope with `request_id`. S3: heading/paragraph chunking with exact offsets, Titan embedder, OpenSearch index mapping and bulk writes by `{doc}:{ordinal}`, idempotent ingestion worker with `ensure_index`, `/query` with BM25 and k-NN both filtered by workspace and fused by RRF (k = 60), 503 `retrieval_unavailable`. 72 API tests pass against fakes, including the `domain/` import boundary and a fake index that honours the filter as written. S4: `apps/web`, Next.js 16.3.5 static export (`trailingSlash`), DESIGN §3 tokens with shadcn variables mapped onto them, Geist via the `geist` package, Phosphor; `/` (New workspace, and Open demo workspace when `NEXT_PUBLIC_DEMO_WORKSPACE_ID` is set) and `/app?ws=`; `lib/api.ts` validates every response with zod and raises `ApiError` with `request_id` (8 vitest tests); per-file upload cards (pre-signed POST over XHR with progress, `complete`, 1.5 s polling to `ready`, duplicate and failure states); ask box with chunk cards in the evidence panel; `amplify.yml` with CSP and security headers. Checked 2026-09-17 in the in-app browser at 1440 and 1024 against a local server running the real API handlers over the test doubles: workspace created, two files reached `ready`, a `.pdf` was rejected with its request ID, a duplicate showed "Already indexed as", a question returned chunk cards, an unknown workspace showed "Workspace not found"; the production build under the amplify.yml CSP loaded fonts and called the API with no CSP violations. S5: `.github/workflows/ci.yml` adds `web` (frozen pnpm install, lint, typecheck, vitest, build) and `api` (`uv lock --check`, frozen sync, ruff, pytest, requirements.txt in sync with uv.lock, cfn-lint, `sam validate --lint`); all four jobs green on GitHub for `bd97894` (run 35234951782). The kit README is replaced by the product README, keeping the Claude Code section. S1 deployed 2026-09-18 with SAM 1.166.2, built without Docker against the uv-managed Python 3.12 (`uv pip install pip` into `services/api/.venv` first, because the SAM pip builder needs pip). Stack `crownx`, CREATE_COMPLETE, outputs: API `https://7qo4ij10i6.execute-api.ap-south-1.amazonaws.com`, bucket `crownx-documentsbucket-oyraa82bziwc`, table `crownx-MetadataTable-7LVFT8NPNPO7`, search domain `search-crownx-search-sj7fcsryhwearznl4jkny332f4.ap-south-1.es.amazonaws.com`, ingest function `crownx-ingest`. `ensure_index` returned `{"status":"ok","created":true}`; `GET /health` returns `ok` with config, table, bucket and index all `ok`. Live end to end: workspace created, `demo/SCENARIO.md` uploaded to S3 with the pre-signed POST (HTTP 204), `complete` computed the checksum and queued ingestion; the worker parses and chunks, then fails at embedding with Bedrock's `Operation not allowed` (B4). First live deploy found a real bug: `complete` returned 500 because botocore's `StreamingBody.__enter__` hands back the raw urllib3 response, which has no `iter_chunks`; fixed in `adapters/s3.py` with a regression test that uses a real `StreamingBody` (74 API tests). Live checks that need a model wait for B4 |
| M2 | Grounded answers + eval baseline | not started | none | none | |
| M3 | Contradictions + conflict inspector | not started | none | none | |
| M4 | Timeline, polish, reliability | not started | none | none | |
| M5 | Workflow Learning Lite (gated) | not started | none | none | Only if M4 is verified by Saturday evening |
| M6 | Freeze and submit | not started | none | none | |

## M0 facts (bootstrap session, 2026-09-16 23:40 to 2026-09-17 18:35 IST)

**Repository:** `github.com/theShivansh/CROWN-X`, created 2026-09-17 13:18 IST (initial commit with an
MIT `LICENSE`), cloned to `Downloads\CROWN-X_\CROWN-X`. Harness commits pushed 2026-09-17 18:24 IST.

**Harness, in the repository** (2026-09-17 13:25 IST), after copying the kit in:
- `python scripts/install_ui_skills.py` installed `design-taste-frontend` at `ccbc156` and
  `ui-ux-pro-max` at `8bd29e7`;
- `python scripts/validate_kit.py`: "Kit valid: 4 agents, 11 skills, hooks wired, no credential
  patterns.";
- `python -m pytest tests -q`: 39 passed;
- committed by explicit path as `75458e2` (107 files), 2026-09-17 13:27 IST.

The harness was not live in the bootstrap session: Claude Code started one folder above the kit, and
settings load at session start, so no SessionStart line appeared and `git add -A --dry-run` was not
denied. Check the SessionStart line, the `git add -A` denial and the Playwright tools at the next start.

**Tools** (Windows 11, checked 2026-09-17 18:25 IST):

| Tool | Result | Needed for |
|---|---|---|
| python | 3.11.9 (Microsoft Store build) | hooks and scripts |
| uv | 0.12.15; uv-managed CPython 3.12.14 runs (its install prints a "minor version link" warning) | API dependencies and the 3.12 runtime |
| pytest, ruff | 9.1.1, 0.16.3 | hook tests, Stop gate |
| node, pnpm | v22.19.0, 10.33.0 | web |
| git | 2.50.0.windows.1, user `theshivanshshukla` | commits |
| aws | aws-cli/2.36.47, Region `ap-south-1`, IAM user `CROWN-X` | every AWS fact |
| sam | not installed | build and deploy (B5) |
| docker | not installed | `sam build --use-container`, `sam local`, the Build It fallback (B7) |
| gh | not installed | optional |

**AWS account** (read-only CLI calls, account ending 4806):
- 13:25 IST: the CLI used long-lived **root** access keys, root MFA was off and there were no IAM
  users. The user fixed this; at 18:24 IST `aws sts get-caller-identity` shows the IAM user `CROWN-X`,
  and `aws iam get-account-summary` shows root MFA on, no root access keys, one IAM user.
- `aws freetier get-account-plan-state`: **Free plan**, active, $100.00 credits, expires 2027-03-16 (B8).
- `aws budgets describe-budgets`: no budgets (B8).
- `aws bedrock get-use-case-for-model-access`: the Anthropic form isn't filled out, and the user can't
  submit it, so Claude is dropped (ADR-013).
- **Every Bedrock runtime call is denied** (Nova 2 Lite, gpt-oss-120b, Qwen3 235B, Titan V2 at 18:25
  IST): "Your account is currently being verified … If you are still receiving this message after more
  than 2 hours, please let us know by writing to aws-verification@amazon.com." The applied Bedrock
  quotas read 0 against defaults of 2,000-10,000 requests a minute. Control-plane reads (model lists,
  OpenSearch, Lambda, S3) work (B4).

**Region:** `ap-south-1`, ADR-012 (accepted). OpenSearch 3.7 offers m7g.medium.search with encryption at
rest there.

**Models:** ADR-013 (proposed). Without Anthropic, the candidates to measure are Qwen3 235B A22B 2507
(in-Region, tool calling and structured outputs), gpt-oss-120b (in-Region, structured outputs) and
Amazon Nova 2 Lite (global profile, tool calling); embeddings are Titan Text Embeddings V2, on-demand
in-Region. The measurement script sends the same grounded prompt with an injection line and a forced
`submit_answer` tool, three runs per model, and checks the output against the answer contract.

**Retrieval store:** ADR-011, proposed: a single-node OpenSearch Service domain, about $5 for 96 hours
in Mumbai.

## Blockers
| ID | Blocker | Owner | Closes when |
|---|---|---|---|
| B2 | Submission deadline not published | organisers; you re-check the schedule page | the deadline and its time zone are recorded above |
| B4 | AWS hasn't finished verifying the account (created 2026-09-17 00:05 IST). Re-checked 2026-09-18: `invoke-model` and `converse` both return `ValidationException: Operation not allowed` for Titan V2, Qwen3 235B and Nova 2 Lite, and `On-demand model inference requests per minute` reads 0. Everything else in the account works: the whole stack deployed and runs | you | you've written to aws-verification@amazon.com; a Titan V2 `invoke-model` call succeeds; S0's measurement runs |
| ~~B5~~ | Closed 2026-09-18: SAM CLI 1.166.2 installed at `C:\Program Files\Amazon\AWSSAMCLIin\sam.cmd` (not on this shell's PATH; call it by full path) | you | closed |
| B7 | Docker not installed. The user chose to skip it on 2026-09-18; `sam build` works without it, and the Build It fallback stays unavailable | you | only if the Build It fallback is needed |
| B8 | Free plan ($100 credits) and no budget; check-in unconfirmed. Free plans can't redeem other promotional credits, and the account closes when the credits run out, which would take the demo URL down within 30 days of steady spend | you | checked in; Paid-plan decision made and the event code redeemed; an AWS Budgets alert exists |
| B9 | Claude Code not yet started at the repository root | you | SessionStart line appears; `git add -A` denied; Playwright tools present |

## Risks
| Risk | Severity | Mitigation |
|---|---|---|
| Scope creep | high | Frozen milestones, kill criteria, Parking lot |
| Account verification delays every Bedrock call and possibly resource creation | high | Build the no-AWS slices first (S2, S3 domain, S4); escalate by email (B4); the triage prompt's Build It fallback if it isn't cleared by Thursday evening |
| Deployment eats day 1 | high | M1 deploys as soon as SAM and verification allow; Build It fallback decided by Thursday evening |
| OpenSearch domain creation slows the first deploy | medium | Deploy infrastructure first and write code while the domain creates (ADR-011) |
| The chosen open-weight model is weaker than Claude at grounded answers | medium | Measure three candidates (ADR-013); citation validation in code drops unsupported claims |
| Free plan closes the account when credits run out | high | Budget alert; teardown plan; Paid-plan decision (B8) |
| Local Python 3.11 against the Lambda 3.12 runtime | medium | uv-managed 3.12 for the API; `sam build --use-container` once Docker runs |
| Poor retrieval | high | Golden set from M2, baseline before tuning |
| False conflict on screen | high | Deterministic predicate; format-equivalence tests |
| Stale answer chosen | high | Explicit selection rule with timestamps and versions |
| Prompt injection via documents | high | Delimited evidence, structured output, test cases |
| AWS cost surprise | medium | Budget alert, limits, one model call per question, teardown |
| Demo fails on the day | high | Record a rough demo Friday; freeze Sunday morning |

## M1 plan (approved by the user, 2026-09-17 10:09 IST)
Decisions made at approval:
- **Region:** `ap-south-1` (ADR-012, accepted).
- **Retrieval store:** ADR-011, a single m7g.medium.search node with 10 GB gp3.
- **Web deploy:** Amplify Hosting connected to the GitHub repo (ADR-014); the user authorizes the GitHub
  app in the Amplify console during S6.
- **Models:** changed 2026-09-17 18:30 IST, because the Anthropic form can't be submitted: measure
  Qwen3 235B, gpt-oss-120b and Nova 2 Lite for answers (used from M2); Titan Text Embeddings V2 for
  embeddings (ADR-013).
- **Repository:** the user created it; Claude made the first commits by path.

The plan, in slices that each end green, committed by path and pushed:
- **S0**, settle and measure: CLI identity and Region (done), one Converse call per answer candidate
  with a forced `submit_answer` tool, one embedding call, quotas, the node type (done), the ADRs (done),
  `/aws-ship check`.
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

Order while B4, B5 and B7 are open: S2, then S3's domain logic and query construction with fakes, then
S4; S0's measurement and S1 as soon as they close.

**S1 deploy runbook** (not run yet; `infra/template.yaml`, `infra/samconfig.toml`, stack `crownx`):
1. `sam build` from `infra/`, with Python 3.12 first on PATH (activate `services/api/.venv`), or
   `sam build --use-container` once Docker runs. Dependencies come from `services/api/src/requirements.txt`.
2. `sam deploy` from `infra/` (asks; shows the change set). The OpenSearch domain takes a while.
3. `aws lambda invoke --function-name crownx-ingest --cli-binary-format raw-in-base64-out --payload '{"action":"ensure_index"}' out.json`.
4. `GET {ApiUrl}/health` should return `status: ok` with table, bucket and index `ok`.
5. In S6, redeploy with `--parameter-overrides AllowedOrigins=http://localhost:3000,https://<amplify-domain>`.
6. In S6, in the Amplify app: set `AMPLIFY_MONOREPO_APP_ROOT=apps/web`, `NEXT_PUBLIC_API_URL` (the `ApiUrl` output) and optionally `NEXT_PUBLIC_DEMO_WORKSPACE_ID`; then replace the two Region wildcards in `amplify.yml`'s `connect-src` with the `ApiUrl` host and `https://<DocumentsBucketName>.s3.ap-south-1.amazonaws.com`.

Kill criterion: if the deployed path isn't working by Thursday evening, run
`prompts/08-TRIAGE-BEHIND-SCHEDULE.md` (Build It fallback). Deferred by the user on 2026-09-17 while AWS
verifies the account (ADR-015); revisit Friday 12:00 IST.

## Verification log
One line per `/verify-stage` run: `date time | milestone | commit | gates | level | failures`
- none yet

## Learning log
Learning is a judged criterion (docs/HACKATHON.md §1). One line per thing learned during the event,
with the date: what, and where it showed up.
- 2026-09-17: a brand-new AWS account can list Bedrock models but is denied every inference call until
  AWS finishes verifying it, with applied quotas at 0; check with one cheap `invoke-model` call on day 1.
- 2026-09-17: Bedrock model access no longer needs per-model enablement, but Anthropic models still
  need a one-time use-case form; open-weight models (Qwen3, gpt-oss) and Amazon Nova don't.
- 2026-09-18: botocore's `StreamingBody.__enter__` returns the raw urllib3 response, not the
  StreamingBody, so `with get_object()["Body"] as body: body.iter_chunks()` raises AttributeError.
  It only showed up against real S3; the fake object store hid it. Test doubles for AWS SDK objects
  should be the real botocore class where one exists.
- 2026-09-18: `sam build` without Docker needs pip inside the Python it builds with; a uv-managed
  venv has no pip until `uv pip install pip`.

## Parking lot
Ideas that don't strengthen the three-minute demo. Revisit after M6.
- Read-only MCP server (`search_documents`, `find_conflicts`, `get_timeline`, `explain_evidence`)
- Human review state for conflicts
- Light theme
