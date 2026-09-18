# CROWN-X handoff

For whoever picks this up next, human or agent. Current as of 2026-09-18 17:10 IST, commit after
`81f4630`. The live state is in `docs/PROGRESS.md`; this file explains how the pieces fit and what to do
first.

## Where things stand
- **M1** (walking skeleton): code done and deployed to `ap-south-1`; `/health` green live. Its live
  done-means wait for Bedrock (B4) and Amplify (S6).
- **M2** (grounded answers): the Offline Gate is GREEN (`docs/CHECKLIST.md`). The External Bedrock
  Gate is blocked only by B4.
- **API:** `https://7qo4ij10i6.execute-api.ap-south-1.amazonaws.com`, stack `crownx`, deployed in
  production mode on Bedrock with **no answer model** configured (`/answer` returns 503
  `answer_unavailable` until one is). Every query currently returns 503 `retrieval_unavailable`,
  because the first step embeds the question with Bedrock.

## First thing tomorrow (2026-09-19)
1. One Titan call:
   `aws bedrock-runtime invoke-model --region ap-south-1 --model-id amazon.titan-embed-text-v2:0 --cli-binary-format raw-in-base64-out --body '{"inputText":"ping"}' out.json`
   (the AWS CLI is at `%LOCALAPPDATA%\Programs\Amazon\AWSCLIV2\aws.exe` if it isn't on PATH).
2. If it works: measure the answer models (S0), then redeploy with
   `sam deploy --parameter-overrides AnswerModelId=<id> AnswerForceTool=<true|false>` from `infra/`
   (build first with `services/api/.venv/Scripts` first on PATH; SAM is `C:\Program Files\Amazon\AWSSAMCLI\bin\sam.cmd`).
3. `python demo/seed.py --api <ApiUrl>`; record the workspace IDs in PROGRESS.
4. `cd services/api && uv run python ../../evals/run.py --api <ApiUrl>`; record the live row in
   BENCHMARKS, accept ADR-013, propose gates in DECISIONS.
5. M1 S6: connect Amplify (you authorize the GitHub app), set `AMPLIFY_MONOREPO_APP_ROOT=apps/web` and
   `NEXT_PUBLIC_API_URL`, narrow `amplify.yml`'s `connect-src`, redeploy with the Amplify origin in
   `AllowedOrigins`, then walk the golden path in a browser.
6. B10: read the gitleaks job summary for run 35337564630 while signed in to GitHub.

If Bedrock still refuses: the triage prompt (`prompts/08-TRIAGE-BEHIND-SCHEDULE.md`) was waived for
Thursday and Friday (ADR-015); decide with the user whether to run it.

## How the code fits (ADR-016)
- `services/api/src/crownx/adapters/providers.py`: `ProviderRouter`, the only place configuration
  becomes an embedder and an answerer. `config.py` refuses any provider the environment doesn't allow:
  production is Bedrock only, `offline-demo` is mock only, development and test allow Bedrock, mock and
  Groq (answers only). The SAM template can only deploy production or offline-demo.
- One OpenSearch index. Chunks carry `embedding_provider`, `embedding_model`, `embedding_version`,
  `vector_dim`; both retrieval clauses filter on workspace plus namespace.
- A question is two calls (ADR-009): `POST /query` stores an immutable snapshot of the evidence;
  `POST /queries/{id}/answer` answers only from that snapshot, and makes no model call when it's empty.
- `domain/answering.py`: `AnswerDraft` in, `finalize()` out. Claims citing unknown or no evidence are
  dropped; the answer text is rebuilt from kept claims; code decides `grounded` / `partial` /
  `insufficient_evidence`.
- The system prompt is a reviewed file: `adapters/prompts/answer_system.md`.

## Running things
All commands are in `CLAUDE.md` (Commands). Offline end to end, no AWS:
- `cd services/api && uv run python ../../evals/run.py --offline` runs the real handlers with the mock.
- For a browser, a local API over the mock providers is a ~100-line script (the in-process client in
  `evals/run.py` is the pattern); point the web app at it with `NEXT_PUBLIC_API_URL`.

## Watch out for
- Offline numbers are pipeline properties, not model quality. Never quote mock answer or retrieval
  numbers as semantic results (BENCHMARKS keeps them in separate tables).
- Switching an environment's embedding provider hides chunks embedded by the other one until the
  documents are re-ingested; that's the namespace working, not data loss.
- The deploy uses `--no-confirm-changeset` only after the user approves in chat; deploys always ask.
- Commit by explicit path; never rewrite history (judges compare it with the event window).
