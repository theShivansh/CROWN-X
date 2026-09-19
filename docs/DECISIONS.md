# CROWN-X decisions

Newest first. Add entries with `/record-decision` (template in that skill). Past 40 entries, move
superseded ones to `docs/decisions/archive.md` and keep their index lines.

## Index
- ADR-020 · 2026-09-19 · M3 claims by rule, extraction confidence defined, conflicts derived on read and scoped to the question · accepted
- ADR-019 · 2026-09-19 · Release gates from the first live runs · proposed
- ADR-018 · 2026-09-18 · Workflow Learning Lite events and miner pulled into M2, suggestions only · accepted
- ADR-017 · 2026-09-18 · Production providers: Groq answers, local ONNX embeddings, OpenSearch kept · accepted
- ADR-016 · 2026-09-18 · M2 architecture lock: providers behind one router, one namespaced index · accepted (production providers superseded by ADR-017)
- ADR-015 · 2026-09-17 · M1's Thursday-evening kill criterion deferred while AWS verifies the account · accepted
- ADR-014 · 2026-09-17 · Web hosting: Amplify Hosting connected to GitHub · proposed
- ADR-013 · 2026-09-17 · Answer and embedding models without Anthropic's use-case form · superseded by ADR-017
- ADR-012 · 2026-09-17 · Region: ap-south-1 (Mumbai) · accepted
- ADR-011 · 2026-09-17 · Retrieval store: a single-node OpenSearch Service domain · accepted
- ADR-010 · 2026-09-16 · Stage prompts and working style written for Opus 5 · accepted
- ADR-009 · 2026-09-16 · A question is two calls: retrieve, then answer · accepted
- ADR-008 · 2026-09-16 · Claude Code harness: one state file, four agents, tested hooks · accepted
- ADR-007 · 2026-09-16 · Third-party UI sources and design skills · accepted
- ADR-006 · 2026-09-16 · Web stack and dark-first design system · accepted
- ADR-005 · 2026-09-16 · Workflow Learning Lite is deterministic and gated behind M4 · accepted (gate amended by ADR-018)
- ADR-004 · 2026-09-16 · Frozen MVP scope with kill criteria · accepted
- ADR-003 · 2026-09-16 · Deterministic contradiction predicate · accepted
- ADR-002 · 2026-09-16 · Evidence-first responses · accepted
- ADR-001 · 2026-09-16 · AWS Ship It first, Build It as fallback · accepted

---

### ADR-020 · 2026-09-19 · M3 claims by rule, extraction confidence defined, conflicts derived on read and scoped to the question
Status: accepted (verified offline and live, 2026-09-19; `docs/BENCHMARKS.md` M3)

**Context:** The M3 stage prompt assumed one Bedrock extraction call per document. On Groq's free tier that call would compete with answers (429s while seeding 7 documents) and the ingest role would need the key, which it deliberately can't read. The user chose rules only. The first offline run then showed that attaching a conflict whenever its chunk is retrieved flags almost every question: workspace A has 17 chunks, top 8 is half of them, and the brief PDF is one chunk holding both the deadline and the budget cap. Status accuracy fell from 0.825 to 0.275, which is false "Sources disagree" on screen.
**Decision:**
- Claims come from `domain/vocabulary.py` triggers plus a typed value in the same sentence (`domain/claims.py`). Quotes are exact slices, so every claim is grounded by construction. Lines matching `instruction_like` are never sources.
- `confidence.extraction` = trigger strength (1.0 label, 0.9 phrase ≤8 words away, 0.8 further) × value certainty (1.0 explicit, 0.9 year inferred from the document's date, 0.0 unnormalized). It is in `/conflicts`, `/query` and the audit, measured per band in BENCHMARKS, and never shown as a number in the UI (CLAUDE.md rule 10).
- Claims are stored (`CLAIM#…`, replaced per document); conflicts and selection are derived by the pure predicate on each read, with IDs hashed from the sorted claim IDs.
- A conflict joins a query only if a conflicting claim's chunk was retrieved AND the question matches that key's `asks` terms. Both tests are code.
**Rejected:**
- Groq extraction at ingestion: quota contention and key access for the ingest role.
- Conflicts stored at ingestion: parallel ingest Lambdas would race, each missing the other's claims.
- Chunk intersection alone (the stage prompt's rule): measured false conflicts on unrelated questions.
**Consequences:**
- Only mapped wording becomes a claim: 5 keys today, dates, numbers and owners. Free-text and requirement conflicts are a listed limitation.
- A paraphrased question that names none of a key's `asks` terms shows no conflict card. That is a missed conflict, never a false one.
- Adding a key means adding its triggers and `asks` terms, with tests.
**Verify / revisit if:**
- `services/api/tests/test_claims.py`, `services/api/tests/test_conflicts_api.py` and the offline eval (contradiction precision 1.0 is a gate in `evals/run.py`) stay green.
- Revisit when a real team's documents use wording the vocabulary misses, measured by extraction recall on a new corpus.

### ADR-019 · 2026-09-19 · Release gates from the first live runs
Status: proposed (from live runs 2 and 3 in `docs/BENCHMARKS.md`; confirm or change before M6)

**Context:** EVALUATION.md asks for gates proposed from a live run, not an offline one. Run 2 is the
first live run after the injection fix: 40 M2 cases on the deployed stack with Groq and bge-small.
**Decision (proposed):**
- **Hard gates**, which block a release at any value below the threshold:
  - citation validity, evidence-ID integrity, workspace isolation, injection resistance and the
    zero-model-call path, each 1.0;
  - insufficient-evidence correctness ≥ 0.8.
- **Quality gates**, which block a release when missed on two runs in a row. Each sits about one
  missed case below run 2, because 40 cases give coarse steps (1 case is 0.025 of the pass rate,
  about 0.036 of the answerable metrics):
  - answer value match ≥ 0.9;
  - the groundedness proxy ≥ 0.9;
  - M2 pass rate ≥ 0.9;
  - recall@8 ≥ 0.95 and MRR ≥ 0.85.
- **Latency gates**, measured on the deployed stack: p95 query ≤ 1.5 s and p95 answer ≤ 4 s.
- **Reported, never gated:** the fallback rate (it depends on the free-tier pace), and the paraphrase
  set (14 cases, written by us).
**Rejected:** gates at run 2's exact values (one unlucky case would fail a release); gates from the
offline run (its answers are scripted).
**Consequences:** `evals/run.py --api` checks the hard gates today (exit code). The quality and
latency gates are read from the report until M6 wires them into `/release`.
**Verify / revisit if:** the golden set grows, the corpus grows past one screen of chunks, or a model
or embedding change moves any metric by more than one case.

### ADR-018 · 2026-09-18 · Workflow Learning Lite events and miner pulled into M2, suggestions only
Status: accepted (the user required it in M2 on 2026-09-18; this amends ADR-005's M4 gate)

**Context:** ADR-005 kept Workflow Learning Lite behind M4 so it couldn't endanger the core demo. The
user asked for it in M2, limited to event logging, stored events and suggestions with confidence, and
explicitly no automation.
**Decision:**
- Events are written server-side only, during upload, ingestion, questions and answers, as an
  append-only stream per workspace (`SK EVENT#{ts}#{event_id}`, conditional put, idempotent by
  `event_id`). An event holds a type and scalar attributes: IDs, counts, statuses, timings. Never
  document text, questions or answers (the model forbids nested values). Timestamps are strictly
  increasing per process so one request's events keep their order. A failed event write is logged
  and never fails the request.
- The miner (`domain/workflow.py`) is pure and deterministic:
  - normalizes events to three steps (`add_document`, `ask_question`, `read_answer`);
  - splits sessions on a 30-minute gap and collapses consecutive repeats;
  - counts contiguous, non-overlapping n-grams of length 3 to 7;
  - keeps sequences with support ≥ 3 and at least 3 different steps;
  - drops a sequence that is contained in a longer one with the same support.
- Scores are defined in every response. `support` is the number of occurrences, and `recency` is the
  last one's end. `confidence` is support divided by how often the first step occurs, which stays
  between 0 and 1. The workflow-learning skill's definition (support over sessions containing the
  first step) can exceed 1 when a pattern repeats within a session, so it was not used.
- `GET /workspaces/{ws}/workflow-suggestions` is read-only, returns `automation: "none"`, and uses no
  model, not even for naming. There's no save, dismiss or UI yet (M5); rule 10 keeps the confidence
  number out of the UI until its presentation is defined.
**Rejected:** suggestions from a model (not reproducible; ADR-005); client-side events for "open
evidence" and similar (needs a write endpoint and abuse limits, M5).
**Consequences:** every upload and question adds one to three small DynamoDB items. The rule of at
least 3 different steps was added after the first run of our own synthetic benchmark. That run found
alternating ask/read fragments outranking the planted workflow (precision 0.33). The benchmark is
synthetic and written by us, so its 1.0 shows that the rules do what they say, not that the
suggestions are useful.
**Verify / revisit if:** `services/api/tests/test_workflow.py` (normalization, support, near misses, duplicates,
determinism, trace links, scoping, non-blocking writes) and `evals/workflow_eval.py` pass; revisit in
M5 with client events and real usage.

### ADR-017 · 2026-09-18 · Production providers: Groq answers, local ONNX embeddings, OpenSearch kept
Status: accepted (the user, 2026-09-18, after the organisers confirmed by email that Bedrock can be skipped)

**Context:** Bedrock stayed refused (B4). Titan embedded every chunk and question, and ADR-016 allowed
only Bedrock in production, so retrieval was down, not just answers. The organisers confirmed that
Bedrock isn't required. The user chose Groq `openai/gpt-oss-120b` for answers and asked for a free,
local retrieval stack. The user's reference design was FAISS + BM25 with e5 embeddings, RRF and a
reranker.
**Decision:**
- Answers come from Groq `openai/gpt-oss-120b`, falling back to `openai/gpt-oss-20b`. The call uses the
  same system prompt, evidence rendering and forced `submit_answer` tool as before, and
  `reasoning_effort: low`. `finalize()` still drops any claim citing unknown evidence.
- Reliability layer, in this order, inside a 26 s deadline:
  1. A timeout retries once.
  2. A 429 retries once, only if `Retry-After` ≤ 2 s.
  3. Anything else falls back once to the fallback model.
  4. If that fails too, the request returns 503 `answer_unavailable`.
  Every attempt (model and outcome) goes into the audit record, the structured log and the `/answer`
  response as `answered_by_model` and `attempts`.
- The Groq key is a SecureString in SSM Parameter Store, created by a person outside the stack. The
  API role may `ssm:GetParameter` that one ARN only. The key is read once per cold start and never
  logged, described or put in the template.
- Embeddings run locally in the Lambdas with ONNX Runtime and `tokenizers` (no torch): `bge-small-en-v1.5`
  int8 (34 MB, 384 dimensions, CLS pooling, BGE's query instruction). `multilingual-e5-small` int8
  (118 MB, `query:`/`passage:` prefixes, mean pooling) stays selectable by parameter.
  - Models are published to `s3://<bucket>/models/<name>/` by `scripts/fetch_models.py`, pinned to a
    Hugging Face commit.
  - Each Lambda copies its model to `/tmp` once and refuses a file whose sha256 differs from the
    stack parameter.
- OpenSearch stays the production index. The user chose it over FAISS in Lambda: BM25 plus Lucene
  HNSW, workspace and namespace filters inside both queries, and RRF (k = 60). A new index,
  `crownx-chunks-v2`, holds the 384-dimension vectors; embedding version 2.
- Retrieval pipeline:
  1. 15 candidates each from BM25 and k-NN.
  2. RRF.
  3. Near-duplicates within one document removed (Jaccard ≥ 0.9; passages from different documents
     are never merged, because M3 needs agreement to stay visible).
  4. Optional cross-encoder rerank of the top 8.
  5. The top 8 become evidence.
- FAISS `IndexFlatIP` and `rank_bm25` BM25Okapi are the offline evaluation's local index, as dev
  dependencies only. `evals/run.py --compare` measures BM25, dense, hybrid and hybrid + rerank for each
  local model.
- Tests never touch the network. `MockGroqTransport` scripts Groq's responses under the real
  `GroqAnswerer`: ok, invented ID, malformed JSON, no tool call, timeouts, 429s and 500s. An autouse
  socket guard fails any outbound connection. The scripted transport is refused in production.
- Measured choices (2026-09-18, `docs/BENCHMARKS.md`):
  - bge-small over e5-small, by the pre-set rule (better MRR, no worse recall@8). Combined hybrid MRR
    over both sets: 0.832 vs 0.825, with equal recall@8. e5 wins on the golden set (0.952 vs 0.917),
    bge on paraphrases (0.661 vs 0.572). I expected e5's multilingual training to win the 4 Hinglish
    questions, but it didn't: bge scored 0.833 against e5's 0.619, because these questions are
    mostly English words. bge is also a quarter of the size, which makes cold starts faster. The
    margin is small and the set is small (42 cases), so this is a measured default, not a finding.
  - The reranker is off in production by the pre-set rule: it must win on MRR within +150 ms p95. It
    wins on MRR (golden 0.95 → 1.0, paraphrase 0.57 → 0.74) but adds about 300-600 ms p95 on a laptop CPU.
    Its recall@8 is unchanged, so the answer model sees the same passages either way.
**Rejected:**
- FAISS + BM25 files in S3 per workspace: new persistence and concurrency code, weaker AWS story, and
  the user preferred OpenSearch.
- A hosted embedding API: another external dependency and rate limit.
- torch in Lambda: too big for a zip package.
- Keeping Bedrock as the only production provider: blocked for an unknown time.
- A local LLM fallback: no local model fits a Lambda.
**Consequences:**
- The two Lambdas grow to 2,048 MB, because ONNX is CPU-bound.
- Cold starts download about 135 MB from S3.
- Groq's free-tier limits apply to live runs: `evals/run.py --api` paces answers and retries 503s.
- Titan-namespace chunks from M1 are hidden and never reused.
- ADR-013 is superseded.
- ADR-016's rules stand except its production provider list: production allows groq/onnx (or
  bedrock), never the mock.
**Verify / revisit if:**
- `test_providers.py`, `test_groq_reliability.py`, `test_onnx_models.py`,
  `test_retrieval_pipeline.py`, `test_observability.py` and `test_infra.py` pass.
- The live gate measures groundedness and latency.
- Revisit the reranker if it can run in under 150 ms on Lambda, or if the corpus grows beyond one
  screen of chunks.

### ADR-016 · 2026-09-18 · M2 architecture lock: providers behind one router, one namespaced index
Status: accepted (the user set it on 2026-09-18 as "ADR-014"; that number was already Amplify hosting)

**Context:** Bedrock inference is refused until AWS verifies the account (B4), but M2 has to be built
and proven today, and nothing built for the blocked path may leak into production. The rules had to
make "switching providers" a configuration change and keep test answers out of real metrics.
**Decision:**
- `ProviderRouter` (`adapters/providers.py`) is the only place configuration becomes an `Embedder` and
  an `Answerer`: `BedrockProvider` (TitanEmbedder, unchanged, plus `ConverseAnswerer`), `MockProvider`
  (`MockEmbedder`, deterministic extractive `MockAnswerer`) and `GroqProvider` (answers only).
- `config.py` refuses to start with a provider the environment doesn't allow: production is Bedrock
  only; `offline-demo` is mock only and must be chosen explicitly; development and test allow all.
  The SAM stack defaults to production and Bedrock, and never allows development or test.
- One OpenSearch index. Every chunk carries `embedding_provider`, `embedding_model`,
  `embedding_version` and `vector_dim`; both retrieval clauses filter on workspace plus namespace, so
  mock and Bedrock vectors never meet. The mock embeds at 1,024 dimensions to share the mapping.
- `/health` returns `providers` (environment, answer and embedding provider and model); the UI shows it.
- `MockAnswerer` cites only the evidence it's given, skips text addressed to an assistant, and says
  "insufficient" when nothing overlaps. The zero-model-call path doesn't depend on the provider.
- Evaluation keeps offline (mock) metrics and live Bedrock metrics apart, and never reports mock
  retrieval or answers as semantic quality. M3 contradiction cases are excluded from M2's headline.
**Rejected:** a mock path hidden in production code behind a flag (anyone could flip it silently); a
second index for mock vectors (doubles the mapping and the cost for no isolation gain).
**Consequences:** M2's offline gate can be green without Bedrock; the Bedrock gate stays open until
B4 closes. Switching an environment's provider hides chunks embedded by the other one until the
documents are re-ingested. ADR-013 stays proposed: `AnswerModelId` is empty by default, so answering
is off (503 `answer_unavailable`) until a measured model is configured.
**Verify / revisit if:** `test_providers.py` (environment rules, router, configuration-only switching,
namespace isolation) passes; revisit when Bedrock is live and the first real benchmark runs.

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
**Verify / revisit if:** a Bedrock runtime call succeeds. Update 2026-09-18: `sam deploy` works and the
stack is live; Bedrock still refused at 15:04 IST, and the user waived the triage check for Friday too.
Next check: 2026-09-19, after AWS verifies the account.

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
