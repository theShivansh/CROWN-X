# CROWN-X handoff

For whoever picks this up next, human or agent. Current as of 2026-09-18 23:50 IST. The live state is
in `docs/PROGRESS.md`; this file explains how the pieces fit and what to do first.

## Where things stand
- **Bedrock is skipped** (ADR-017, organisers' confirmation). Production answers with Groq
  `openai/gpt-oss-120b`, falling back to `openai/gpt-oss-20b`. It embeds with a local ONNX model,
  `bge-small-en-v1.5` int8, chosen by measurement. OpenSearch stays.
- **M2 Offline Gate:** GREEN, re-run after ADR-017/018 (`docs/CHECKLIST.md`).
- **M2 Live Gate:** not run. It needs the Groq key in SSM (B11) and a deploy.
- **Deployed stack:** `https://7qo4ij10i6.execute-api.ap-south-1.amazonaws.com`, stack `crownx`. It
  still runs the pre-ADR-017 code: Bedrock providers and no answer model. Redeploying switches it.

## First thing next session
1. **You:** create the key as an SSM SecureString, in your own terminal, so it never passes
   through an agent:
   `aws ssm put-parameter --region ap-south-1 --name /crownx/groq-api-key --type SecureString --value <key>`.
2. Publish the models and note the sha256 values it prints:
   `python scripts/fetch_models.py --only bge-small-en-v1.5-int8 --only ms-marco-MiniLM-L-6-v2-int8 --publish <DocumentsBucket>`.
3. Build and deploy (ask first), from `infra/`:
   - Build with `services/api/.venv/Scripts` first on PATH. SAM is at
     `C:\Program Files\Amazon\AWSSAMCLIin\sam.cmd`.
   - `sam build`. Check that the zip stays under 250 MB unzipped: onnxruntime, tokenizers and numpy
     for arm64. If the arm64 wheels fail, switch `Architectures` to x86_64.
   - `sam deploy --parameter-overrides OnnxModelSha256=<bge sha> RerankerModelSha256=<reranker sha>`.
   - Invoke `crownx-ingest` with `{"action":"ensure_index"}` to create `crownx-chunks-v2` (384-d).
4. Check `/health` shows `answer_provider: groq` and `embedding_provider: onnx`. Then
   `python demo/seed.py --api <ApiUrl>` and record the workspace IDs in PROGRESS.
5. Run the live eval: `cd services/api && uv run python ../../evals/run.py --api <ApiUrl> --pace 2.5`.
   Record the live row in BENCHMARKS and propose the gates in DECISIONS.
6. M1 S6: connect Amplify (you authorize the GitHub app) and set `AMPLIFY_MONOREPO_APP_ROOT=apps/web`
   and `NEXT_PUBLIC_API_URL`. Narrow `amplify.yml`'s `connect-src`, redeploy with the Amplify origin in
   `AllowedOrigins`, and walk the golden path in a browser.
7. B10: read the gitleaks job summary for run 35337564630 while signed in to GitHub.

## How the code fits (ADR-016, ADR-017, ADR-018)
- `adapters/providers.py` `ProviderRouter` is the only place configuration becomes an embedder, an
  answerer and an optional reranker. `config.py` refuses:
  - the mock in production;
  - the scripted Groq transport in production;
  - an ONNX model without a pinned sha256.
- `adapters/groq.py` holds the reliability layer: a timeout retries once, a 429 with Retry-After of
  2 s or less retries once, anything else falls back once, and then comes `answer_unavailable`. It
  stays inside a 26 s deadline and records every attempt. `adapters/groq_mock.py` scripts Groq
  for tests and the offline eval.
- `adapters/onnx_models.py` runs the ONNX embedder and cross-encoder, with an S3 → `/tmp` cache and a
  sha256 check.
- `app/service.py` query pipeline: 15+15 candidates, RRF, same-document dedup, optional rerank of the
  top 8, then the top 8 are stored as the immutable evidence snapshot (ADR-009).
- One OpenSearch index per vector size (`crownx-chunks-v2`). Chunks carry the embedding namespace, and
  both retrieval clauses filter on workspace plus namespace.
- `domain/answering.py`: `finalize()` drops claims citing unknown evidence; code decides the status.
- Workflow events (`app/events.py`, `EVENT#` items) and the miner (`domain/workflow.py`) are
  read-only: `GET /workspaces/{ws}/workflow-suggestions`.
- The structured log, the audit record and the `/answer` response all name the environment, the
  providers and `answered_by_model`.

## Running things
All commands are in `CLAUDE.md` (Commands). Offline end to end, no AWS:
- `cd services/api && uv run python ../../evals/run.py --offline` runs the real handlers with the
  production Groq adapter over the scripted transport and a local BM25 + FAISS index;
  `--embedding bge-small-en-v1.5-int8` uses the real local model (after `scripts/fetch_models.py`).
- `... --compare [--dataset paraphrase]` is the retrieval benchmark; `evals/workflow_eval.py` the miner's.
- For a browser, a local API over the mock providers is a ~100-line script (the in-process client in
  `evals/run.py` is the pattern); point the web app at it with `NEXT_PUBLIC_API_URL`.

## Watch out for
- Offline answers are scripted: never quote them as model quality. Offline retrieval with a real
  local model is real retrieval, but on a 17-chunk corpus (recall@8 saturates).
- Groq's free tier rate-limits: never point tests or CI at the real API; live evals pace themselves.
- Switching an environment's embedding provider hides chunks embedded by the other one until the
  documents are re-ingested; that's the namespace working, not data loss.
- The deploy uses `--no-confirm-changeset` only after the user approves in chat; deploys always ask.
- Commit by explicit path; never rewrite history (judges compare it with the event window).
