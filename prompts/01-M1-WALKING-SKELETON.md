# 01 · M1 · Walking skeleton, deployed

Build the thinnest path from a browser to AWS and back, and deploy it today: upload a Markdown file,
index it, ask a question, and get back chunks with IDs that resolve to that file, all on the deployed
URL. Nothing in this milestone is clever. Its value is that every later milestone lands on
infrastructure that already works in production. Deployment is the step most likely to eat a day, and
"Built on AWS" decides most of the score.

## Read first
`CLAUDE.md`, `docs/MILESTONES.md` (M1), `docs/ARCHITECTURE.md` (all), `docs/SRS.md` §§3-6,
`docs/SECURITY.md` §§2, 4, `docs/DESIGN.md` §§3-5, `docs/DECISIONS.md` (ADR-001, ADR-006, ADR-011),
`.claude/skills/aws-ship/SKILL.md`. Read `docs/PROGRESS.md` for the region, the model shortlist and any
blockers from the bootstrap.

## Decisions to settle first
Record each with `/record-decision`:
- **Region** (from the bootstrap).
- **Retrieval store:** confirm ADR-011.
- **Answer model and embedding model.** Make one small Bedrock Converse call to each answer-model
  candidate, with the same short prompt, and one embedding call. Record for each: latency, whether
  tool-based structured output works, and the per-minute quotas that `/aws-ship check` reads. Pick the
  answer model with the best latency among those that return valid structured output. Model IDs go in
  SAM parameters and environment config only.
- **Deploy path for the web app:** Amplify Hosting connected to the GitHub repository (the user
  authorizes this in the console), or manual deploys of the static build if the user prefers.

## Repository layout
Later milestones and prompts assume these paths, so create exactly this shape:

```text
apps/web/                     Next.js App Router, TypeScript strict, static export
services/api/
  pyproject.toml              uv-managed; ruff config inherits the root ruff.toml
  src/crownx/
    domain/                   pure logic: models, chunking, retrieval fusion, later claims and conflicts
    adapters/                 s3, dynamo, opensearch, bedrock behind Protocols in adapters/ports.py
    app/                      Lambda handlers: api.py (HTTP), ingest.py (ingestion worker)
    config.py                 environment settings, validated with pydantic-settings
  tests/
infra/template.yaml           AWS SAM template for the whole backend
amplify.yml                   Amplify monorepo build settings (appRoot apps/web)
demo/                         SCENARIO.md now; documents in M2
evals/                        golden set and runner, from M2
```

`domain/` never imports boto3, opensearch-py or anything in `adapters/`. Write a test that parses the
package with `ast` and fails if it does; that keeps the conflict engine testable without AWS.

## Backend

**Runtime and libraries.**
- Python 3.12, managed with uv. Export `requirements.txt` for SAM builds with `uv export --no-dev`.
- Libraries: pydantic v2, pydantic-settings, boto3, opensearch-py, and aws-lambda-powertools
  (`Logger` with correlation IDs, `APIGatewayHttpResolver` for routing).
- pypdf arrives in M2.

**Endpoints this milestone** (contracts in `docs/SRS.md` §3; implement the M1 subset exactly):
- `GET /health`: checks that config loads and that the table, bucket and index are reachable. Returns
  per-dependency status, never secrets.
- `POST /workspaces`: creates a workspace with an unguessable ID (`ws_` + 22 URL-safe random chars).
  For the event, this ID is the access boundary (SECURITY §3).
- `POST /workspaces/{ws}/documents/upload-url`:
  - Validate filename extension (`.md`, `.txt` now; `.pdf` in M2) and declared size.
  - Create the document record with status `pending`.
  - Return an S3 **pre-signed POST** with a `content-length-range` condition, so S3 itself enforces
    `MAX_UPLOAD_BYTES`.
  - Key `ws/{ws}/{doc}/{sanitized-filename}`; expiry 5 minutes.
- `POST /workspaces/{ws}/documents/{doc}/complete`:
  - `head_object` to confirm size and content type, then compute the SHA-256 checksum.
  - Record a checksum lock item with a conditional put (`attribute_not_exists`). If the checksum
    already exists in this workspace, mark this document as a duplicate pointing at the original and
    return it.
  - Otherwise invoke the ingestion Lambda asynchronously (`InvocationType="Event"`) and return
    status `queued`.
- `GET /workspaces/{ws}/documents`: documents with status, stage and error.
- `POST /workspaces/{ws}/query`: embed the question and run BM25 and k-NN retrieval, both filtered by
  `workspace_id` inside the query. Fuse with reciprocal rank fusion (k = 60) in `domain/`, and return
  the top `RETRIEVAL_TOP_K` chunks with IDs, spans, scores and ranks. No answer model yet.

**Errors.** Every error uses one envelope: `{"error": {"code", "message", "request_id"}}`, with the
status codes in SRS §6. Every response carries `request_id`, and the Logger includes it on every line.

**Ingestion worker** (`app/ingest.py`):
- Read the object and decode text.
- Chunk by heading, then paragraph, at about 1,000 characters with 120 characters of overlap, keeping
  character offsets and the nearest heading as `page_or_section`.
- Embed in batches.
- Bulk-index into OpenSearch with the SRS §4 chunk fields.
- Update the document through the stages `parsing`, `indexing`, then `ready` with a chunk count, or
  `failed` with a reason.

The worker must be safe to run twice for the same document: deterministic chunk IDs
(`{doc}:{ordinal}`), index by ID, and a status guard.

**Data.**
- DynamoDB: one table, on-demand billing.
  - `PK = WS#{ws}`; `SK` prefixes `META`, `DOC#{doc}`, `CHECKSUM#{sha256}`, `QUERY#{id}` (M2),
    `CLAIM#…` and `CONFLICT#…` (M3), `EVENT#…` (M5), `AUDIT#{iso-ts}#{request_id}`.
  - One GSI only if a query needs it; say which.
- OpenSearch index `crownx-chunks`:
  - `workspace_id`, `document_id`, `chunk_id`, `version_label`, `page_or_section`: keyword
  - `text`: text
  - `embedding`: knn_vector sized to the embedding model
  - `source_timestamp`, `uploaded_at`: date
  - `char_start`, `char_end`: integer

  Create it idempotently from the ingestion role at first use, or with a one-off script. Say which.

**Infrastructure** (`infra/template.yaml`, AWS SAM):
- HTTP API with CORS allowed only for the Amplify domain and `http://localhost:3000`, plus route
  throttling.
- Two functions: `ApiFunction` and `IngestFunction`, each with its own least-privilege role. No `*`
  actions or resources.
- S3 bucket: block public access, CORS for POST from the same origins, and a lifecycle rule expiring
  objects after 30 days.
- DynamoDB table, the retrieval store resources for the chosen option, and log groups with 14-day
  retention.
- Parameters: model IDs, allowed origins, limits.
- Outputs: API URL, bucket name, table name.

`sam validate --lint` must pass.

## Web
- Next.js App Router, TypeScript strict, `output: "export"` (see ARCHITECTURE §8). Set
  `images.unoptimized`, because static export has no image server.
- Tailwind v4, with the `@theme` block from `docs/DESIGN.md` §3 pasted into `app/globals.css`. Map the
  shadcn/ui CSS variables to those tokens.
- Geist and Geist Mono through `next/font`; `@phosphor-icons/react`; and `motion` (M3 uses it).
- **Routes:**
  - `/`: a plain page with "Open demo workspace" and "New workspace".
  - `/app`: the workspace, keyed by `?ws=`. Static export can't pre-render unknown dynamic segments, so
    the workspace ID lives in the query string.
- **API client** (`lib/api.ts`): one module; every response validated with zod against the SRS shapes;
  errors turned into a typed `ApiError` carrying `request_id`. Base URL from `NEXT_PUBLIC_API_URL`.
- **Upload:** pre-signed POST sent with `XMLHttpRequest` for progress, then `complete`, then poll the
  document list every 1.5s until the document is `ready` or `failed`. Each file's card resolves on its
  own.
- **Ask:** a text input. Results render as a list of chunk cards with document name, section and the
  matched text. Layout follows the three-pane shell in DESIGN §5, unstyled beyond tokens; polish is M4.
- **Security headers:** static export can't set headers from Next.js. Put CSP,
  `X-Content-Type-Options`, `Referrer-Policy` and `frame-ancestors` in Amplify custom headers
  (`customHeaders` in `amplify.yml`), with `connect-src` naming the API URL and the S3 bucket endpoint.

## CI
Add two jobs to `.github/workflows/ci.yml`, next to the harness jobs:
- **web:** `pnpm install --frozen-lockfile`, then lint, typecheck, test (vitest) and build.
- **api:** `uv sync --frozen`, `ruff check`, `pytest`, `sam validate --lint`.

Fill in the commands in `CLAUDE.md` the moment each one works.

## Tests this milestone needs
- **Domain:** chunk boundaries and offsets round-trip to the original text; RRF ordering is
  deterministic, including ties; the boundary test on `domain/`.
- **API with fake adapters:**
  - upload-url rejects wrong extensions and oversize declarations with the SRS errors;
  - `complete` on a known checksum returns the duplicate;
  - IDs from another workspace return 404;
  - every error carries `request_id`.
- **Query construction:** the OpenSearch request body contains the `workspace_id` filter in both the
  BM25 clause and the k-NN clause.
- **Ingestion:** running the worker twice for one document leaves one set of chunks.
- **Web:** the API client rejects a malformed response and surfaces `request_id`.

Test doubles live only under `tests/`; the deployed code has no mock path.

## Deploy and prove it
1. `/aws-ship check`, then `/aws-ship deploy` (it asks before deploying).
2. Web: connect Amplify, or deploy manually, with `NEXT_PUBLIC_API_URL` set.
3. On the deployed URL, in the browser through Playwright MCP:
   - create a workspace;
   - upload `demo/SCENARIO.md` itself as the test Markdown file;
   - watch it reach `ready`;
   - ask "What is the submission deadline?" and confirm the returned chunk IDs belong to that
     document.
4. Find that request in CloudWatch Logs by its `request_id`.
5. `/run-skill-generator`, so `/run` and `/verify` know how to start the web app and API locally.

## Out of scope
Answer generation, PDFs, claims, conflicts, timeline, visual polish, landing page design and auth
beyond the workspace ID.

## Done means
- [ ] `/health` green on the deployed API (live)
- [ ] A Markdown file uploaded through the deployed web app reaches `ready` (live)
- [ ] A question on the deployed URL returns chunk IDs that resolve to that file (live)
- [ ] `workspace_id` filter present in both retrieval clauses, and a cross-workspace test passes
  (unit + integration)
- [ ] CI green on push, with web, api, harness and gitleaks jobs (integration)
- [ ] `CLAUDE.md` commands filled in and working; ADRs for region, store, models, deploy path recorded
- [ ] Request found in CloudWatch by `request_id` (integration)

## If it doesn't come together
If the deployed path isn't working by Thursday evening, run `prompts/08-TRIAGE-BEHIND-SCHEDULE.md`. It
covers the Build It fallback: the same code on SAM Local plus OpenSearch in Docker, with the deploy
retried on Saturday morning.

## Finish
- Update `docs/PROGRESS.md`: the M1 row with commit and level, the next-session line pointing at M2,
  blockers, and a verification log line from `/verify-stage M1`.
- Commit by path at each green slice, and push.
- Report in a few sentences: the deployed URLs, which done-means items passed at which level, the
  decisions recorded, and anything the user must do.
