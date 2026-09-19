# CROWN-X writeup

AWS First Commit 2026 · Ship It track · solo · 17-20 September 2026.

- **App:** https://main.d1jy52bqj8dt1h.amplifyapp.com/
- **Repository:** https://github.com/theShivansh/CROWN-X

Every number below is in `docs/BENCHMARKS.md` with its command, commit and date.

## The problem, and who has it
Student and project teams keep their facts in a pile of versions: a brief, a revised spec, an
organiser email, meeting notes pasted from chat. The submission deadline in the brief says 20
September; the organiser moved it to 22 September; the notes confirm 22. Ask a document chatbot
"when is the deadline?" and it answers from whichever passage it retrieved, without saying another
source disagrees. A team finds out when it's too late.

CROWN-X answers from cited passages. When sources disagree it shows both, which one is current, and
the rule that decided it.

## What I built
A deployed web app. You create a workspace, upload Markdown, text or PDF files, and ask questions.
- **Answers with citations.** Each sentence carries citation chips that open the exact passage.
  If nothing supports an answer, it says "Not enough evidence" and makes no model call.
- **A conflict card and inspector.** Both values side by side, with their sources, dates and quoted
  spans, the newer one marked, and the selection rule in words.
- **A value timeline** for a fact, from 20 Sep to 22 Sep, with the change and the conflict marked.
- **Workflow Learning Lite.** When the same steps repeat (ask, inspect the conflict, open the
  timeline, copy the answer), a card suggests saving them as a workflow, with the exact events behind
  it. It never runs anything.
- **The reliability layer:**
  - hourly limits;
  - per-route throttling;
  - the request ID shown on every error card;
  - per-stage latency in the logs;
  - security acceptance tests run against the deployed stack.

## How it works
**Evidence first.** A question is two calls.
1. The first retrieves. BM25 and vector search run in OpenSearch, each filtered by workspace inside
   the query, and are fused by reciprocal rank fusion. The passages are stored.
2. The second call has the model (gpt-oss-120b on Groq) answer over exactly those passages. They're
   given as an escaped data block, never as instructions.
3. Code then keeps only the sentences whose citations all point to retrieved passages.

The status (grounded, partial, conflict, insufficient) is set by code, not by the model's text.

**Conflicts are decided by code, never by a model.** At ingestion, rules extract typed claims: a
trigger phrase plus a date, number or owner in the same sentence, normalized ("22 Sept" is
2026-09-22; "60 rpm" is "60 requests per minute").
- Two claims conflict only when all of these hold: the same fact, the same type, both normalized, the
  same unit, different documents, and different values.
- The current value is chosen by the newest source date, then by version order, then by the latest
  upload. The last is named as the weakest rule. With no ordering signal, nothing is selected.
- On our demo scenario, contradiction precision and recall were both 1.0 offline and on the deployed
  stack. Values that differ only in format, such as "22 Sept" and 2026-09-22, were never flagged.

**Workflow learning is deterministic.**
- Events hold IDs only, and every event is ordered by the server's clock.
- A miner counts step sequences that repeat, contiguously.
- A model is given only the step types and their timings, and suggests a name. Everything else is
  counted.

## Where AWS fits
All in ap-south-1, defined in one AWS SAM template:
- **Amplify Hosting** serves the static Next.js export and rebuilds on every push.
- **API Gateway HTTP API** is the edge: CORS for the app's origin, and per-route throttling
  (answers at 1 request per second, burst 5) as a cost control.
- **Lambda** runs two functions, the API and the ingestion worker, each with its own least-privilege
  IAM role. The embedding model (bge-small, ONNX int8) runs inside the Lambda, so indexing makes no
  paid model calls.
- **S3** takes uploads straight from the browser through a size-limited pre-signed POST. No file
  passes through Lambda, and S3 enforces the size. It also stores the pinned model files.
- **OpenSearch Service** is one index for BM25 plus k-NN, with the workspace filter inside every
  query. A single node, because this is demo scale.
- **DynamoDB**, on demand, keyed by workspace: documents, claims, stored queries, audit records,
  workflow events, saved workflow versions, and hourly quota counters that expire through TTL.
- **CloudWatch Logs and Logs Insights.** Every request logs its route, status, error code and the
  time of each stage. The UI shows a request ID on every error, and a saved query finds that request
  in about five seconds.
- **SSM Parameter Store** holds the Groq key as a SecureString, read once per cold start.

**Measured latency** inside Lambda, p50 / p95:

| Stage | p50 | p95 |
|---|---:|---:|
| Retrieval, end to end | 39 ms | 65 ms |
| Question embedding | 4 ms | 5 ms |
| OpenSearch search | 13 ms | 33 ms |
| Groq answer call | 731 ms | 1153 ms |
| Ingesting a document | 927 ms | 1367 ms |

**Cost reasoning:**
- one model call per question, and zero when nothing was found;
- local embeddings;
- a single-node search domain;
- functions that scale to zero between uses;
- limits counted in DynamoDB before any work is done.

## What was hard
- **Bedrock on a new account.** On day one, the new AWS account could list Bedrock models but was
  denied every inference call while AWS verified it, with quotas at zero. I put the answer model and
  the embedder behind one provider interface and moved to Groq plus local ONNX embeddings (ADR-017).
  Bedrock is still one configuration switch away.
- **Conflicts on every question.** My first rule attached a conflict whenever a conflicting passage
  was retrieved. With top-8 retrieval over a small workspace, that flagged almost every question:
  status accuracy fell from 0.825 to 0.275. A conflict now also needs the question to name the fact
  (ADR-020).
- **Two clocks.** Workflow events came from both the browser and the server. Ordering them by the
  browser's clock scrambled the sequences in my tests. Now the server's clock orders everything, and
  retries are recognised by their event ID (ADR-022).
- **No reserved concurrency.** The account's Lambda limit is 10, and AWS keeps 10 unreserved. Cost is
  bounded by throttling and a DynamoDB quota instead (ADR-021).

## What I learned
- **Check model access with one real call on day one.** Listing models proves nothing.
- **Deciding which conflicts matter to a question is a separate problem from detecting them.**
- **A test that captures a log line doesn't prove it reaches CloudWatch.** The runtime drops standard
  INFO logs in Lambda, and only the Powertools logger's lines arrived.
- **Test doubles should be the real SDK classes where they exist.** Two bugs only appeared against
  real S3 and DynamoDB.
- **Evaluation catches what unit tests normalize away.** The PDF's double spaces showed up as a
  failed value match.

The full list is the Learning log in `docs/PROGRESS.md`.

## Limitations
- The workspace ID is the only access control, and there are no accounts.
- Conflicts cover five facts, with dates, numbers and owners only. The vocabulary and claim
  extraction are English.
- A question that doesn't name the fact shows no conflict card: a conflict can be missed, but one is
  never invented.
- A true fact in the same passage as an injected instruction is refused along with it.
- The workflow suggestions were tested on my own synthetic benchmark and one live trace, not with real
  teams.

## What's next
- **Claim extraction for free-text facts,** with a model allowed to extract but still never to
  decide a conflict.
- **Accounts** (Cognito) and sharing.
- **Weighted fusion** tuned on a separate development set: equal-weight fusion costs about 0.15 MRR
  on our benchmark.
- **Bedrock as the production answer model,** once the account is verified.

## AI coding tools
- **Claude Code with Claude Opus 5** planned, implemented, tested, reviewed and verified each
  milestone. `CLAUDE.md` and `.claude/` hold the working method.
- **GitHub Copilot** gave inline completions.
- The product itself calls `openai/gpt-oss-120b` on Groq to write answers and name workflows.

## Credits
The third-party components, models, fonts and licences are listed in `CREDITS.md`. The demo
documents and the evaluation datasets were written for this project during the event.
