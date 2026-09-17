# 08 · Triage when behind schedule (insert)

Use this when a milestone gate fails, a day's target slips, or deployment is blocked. The goal is a
decision within 20 minutes that protects the one thing judges score most heavily: **a golden path that
works on what gets submitted.** Triage isn't a place to push harder on the thing that's stuck. It's
where scope gets cut on purpose, recorded, and communicated, so the remaining hours go to what the
video will show.

## Read first
- `docs/PROGRESS.md`: the deadline, milestone rows and blockers
- `docs/MILESTONES.md`: the kill criteria for the current and next milestones
- `docs/HACKATHON.md` §§2-3
- the last two verification log entries
- `git log --oneline -15`

## 1. Establish the facts
Answer from observation, not memory. Run what's needed to know each one:
- **Time left** until the submission deadline, and until the next day's gate.
- **Does the golden path work right now on the deployed URL?** Check it with Playwright MCP: upload,
  ask, evidence, conflict, timeline. Which step fails first?
- **What exactly is failing:**
  - the command and its output;
  - the error in CloudWatch by `request_id`;
  - or the blocker, and who owns it (you, AWS quota or access, the user's console step).
- **What's done but unverified**, and what verifying it would take.

## 2. Pick the smallest cut that restores the path
Match the situation, apply the matching cut, and don't combine cuts unless one isn't enough.

| Situation | Cut |
|---|---|
| Deployment blocked (IAM, quota, region, store provisioning) past Thursday evening | **Build It fallback**, below. Retry Ship It Saturday morning with fresh eyes, starting from the exact error. |
| Bedrock model access or quota blocking | Switch to the other shortlisted model in the same region (config and ADR only). If none are available, use a supported region for Bedrock calls alone and state the cross-region latency. |
| Hybrid retrieval quality poor | Semantic-only retrieval, measured, recorded. |
| Claim extraction unreliable for some types | Dates and numbers only (deterministic normalizers); others listed as limitations. |
| Timeline behind on Saturday afternoon | A vertical list of value changes from the same API; the horizontal track is cut. |
| UI polish behind | Finish states and the conflict inspector; drop the landing page, counters and palette in that order. |
| M5 not verified by Sunday 10:00 | Flags off, redeploy, keep it out of the video. |
| Everything behind on Sunday | Submit what works now (M6 §§2-5 in their minimum form), then improve until the deadline. |

## 3. Build It fallback (deployment blocked)
Run the same application code locally on the event's open-source AWS stack, so the project stays
eligible and demoable:
- SAM Local for the API and ingestion functions: `sam build`, then `sam local start-api` with an env
  file for local endpoints.
- OpenSearch in Docker (`opensearchproject/opensearch`, single node, security plugin configured for
  local use only). The adapter selects it with an `OPENSEARCH_ENDPOINT` setting; no code path branches
  on "local".
- DynamoDB Local and S3: DynamoDB Local in Docker, and a local S3 emulator (LocalStack) behind the same
  adapters. Record which one is used.
- Bedrock: it can still be called from local code if model access works. If it doesn't, Build It
  permits a local model, but changing the model changes the product, so record that as an ADR and say
  so in the writeup.
- `docker compose` file in `infra/local/`, with a README section for running the demo locally.

Keep the Ship It retry on the plan: note the exact failure, and the first thing to try when retrying.

## 4. Record and communicate
- ADR via `/record-decision`: what was cut, why (with the observed failure), what it costs the demo,
  and what would reopen it.
- `docs/MILESTONES.md`: adjust the affected milestones' scope and done-means (strike through, don't
  delete).
- `docs/PROGRESS.md`: blocker rows, the revised schedule to the deadline, the next-session line.
- Commit by path.

## Report
In a few sentences:
- what's failing and why;
- the cut chosen and what it costs the video;
- the revised schedule to the deadline;
- what the next hour is spent on;
- anything only the user can unblock, with the exact action.
