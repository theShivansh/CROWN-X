---
description: Prepare, deploy and prove the CROWN-X AWS stack (SAM API, Amplify web) for the Ship It track, with cost guardrails and evidence for the video. Invoke manually; it spends credits.
argument-hint: "[check|deploy|proof|teardown]"
disable-model-invocation: true
---

# AWS ship: $ARGUMENTS

Architecture and IAM rules: `docs/ARCHITECTURE.md` (AWS section) and `docs/SECURITY.md`.
Every command that deploys or deletes is confirmed by the user (permissions `ask` plus guard_bash).

## check: before the first deploy (M1)
1. `aws sts get-caller-identity`: the right account, and not root credentials.
2. Region: record it in `docs/ARCHITECTURE.md` (Configuration). Check Bedrock model access there:
   `aws bedrock list-foundation-models --by-output-modality TEXT` and, if the chosen model needs one,
   `aws bedrock list-inference-profiles`. Record the model ID in config, never in code.
3. Make one real Bedrock call with the smallest prompt. Record its latency and the account's quotas
   for that model (requests and tokens per minute) in DECISIONS: they set the retry and concurrency
   limits.
4. Retrieval store: choose and record (ADR) between the options in ARCHITECTURE, with the hourly
   price checked today for this region. Set an AWS Budgets alert on the account credits.
5. `sam validate` and `sam build` pass.

## deploy
1. Full test suite green, then `sam build`.
2. `sam deploy` (the user confirms). Record stack name and outputs.
3. Web: publish to Amplify with `NEXT_PUBLIC_API_URL` set to the API output. Confirm that the Next.js
   version is supported by Amplify Hosting, or use static export (ARCHITECTURE explains why).
4. Smoke: `/health`, then one upload, ask, conflict round trip against the deployed API, then
   the golden path on the Amplify URL through Playwright MCP.
5. Record URLs, commit and time in `docs/PROGRESS.md`.

## proof: for the video and writeup
- The architecture diagram matches what is deployed: list the stack's resources and compare.
- A CloudWatch log line for a demo request, found by request ID.
- Cost note: services used, why each, and the guardrails (limits, budget alert).

## teardown: after judging only
List what would be deleted and the data lost, then wait for the user to confirm each stack.
