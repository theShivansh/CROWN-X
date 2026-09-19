# Submission sheet (First Commit form)

Paste each block into its field. You submit the form; I record the time and contents in
`docs/PROGRESS.md` afterwards. Only the video link is still to come.

## Track you are submitting for
Ship It

## GitHub link to project
https://github.com/theShivansh/CROWN-X

## Deployed link to project
https://main.d1jy52bqj8dt1h.amplifyapp.com/

## YouTube video demo link
_(paste the unlisted or published link after upload)_

## What does your project do?
CROWN-X answers questions about a team's evolving project documents, and shows where those documents
disagree.

Student and project teams keep their facts across versions: a brief, a revised spec, an organiser
email, meeting notes. The brief says submissions close on 20 September; the organiser moved it to 22
September. A normal document chatbot answers from whichever passage it happens to find and never
says another source disagrees, so teams find out too late.

In CROWN-X you upload the documents and ask a question. Every sentence of the answer cites the exact
passage it came from. If nothing supports an answer, it says "Not enough evidence" instead of
guessing. When two sources give different values for the same fact, CROWN-X shows:
- both sources side by side;
- which value is current (for example, by the newest source date);
- a timeline of how the value changed.

The conflict is decided by deterministic code, never by the AI model. On our demo scenario, conflict
detection was measured at precision 1.0 and recall 1.0, both offline and on the deployed stack.

It also notices when a team repeats the same steps, such as asking, checking a conflict and copying
the answer, and offers to save them as a workflow, showing the exact events it found. Nothing runs
automatically.

## How did you use AWS in your project?
Ship It. It's deployed on AWS in ap-south-1, from one AWS SAM template:
- **AWS Amplify Hosting** serves the Next.js app and redeploys on every Git push.
- **Amazon API Gateway (HTTP API)** is the API edge: CORS, plus per-route throttling as a cost
  control.
- **AWS Lambda** runs two functions (the API and the ingestion worker), each with its own
  least-privilege IAM role. The embedding model (bge-small, ONNX) runs inside the Lambda, so
  indexing costs no model calls.
- **Amazon S3** takes uploads directly from the browser through size-limited pre-signed POSTs, and
  stores the pinned model files.
- **Amazon OpenSearch Service** holds one index for keyword (BM25) and vector (k-NN) search. Every
  query is filtered to its workspace.
- **Amazon DynamoDB** (on demand) holds documents, extracted claims, stored queries, audit records,
  workflow events, saved workflow versions and hourly quota counters, which expire with TTL.
- **Amazon CloudWatch Logs and Logs Insights:** every request logs its request ID and per-stage
  latency. The UI shows the request ID on every error, and a saved query finds it in seconds.
- **AWS Systems Manager Parameter Store** holds the answer model's API key as a SecureString.
- **IAM and AWS CloudFormation (SAM)** give one role per function and a repeatable deploy.

Answers are written by gpt-oss-120b on Groq. On day one, Bedrock inference was blocked while AWS
verified the new account, so the answer model sits behind a provider interface where Bedrock is one
configuration switch (ADR-017).

**Cost guardrails:**
- one model call per question, and none when no evidence is found;
- local embeddings;
- a single-node search domain;
- functions that scale to zero;
- 60 questions per workspace per hour, counted in DynamoDB before any work is done.

**Measured on the deployed stack, p50 / p95:** retrieval 39 / 65 ms inside Lambda, and the answer
call 731 / 1153 ms.

## Blog links
_(optional; add if you publish on AWS Builder Center)_

## Team leader's contributions
Solo project: I did all of it.
- **Product and design:** the problem framing, the three rules (evidence or nothing, code decides
  conflicts, documents are data), the demo scenario, and the UI (conflict inspector, timeline,
  evidence panel, Ask palette, workflow card).
- **Backend:**
  - the ingestion pipeline (Markdown, text and PDF);
  - hybrid retrieval with reciprocal rank fusion;
  - grounded answers with citation checks and prompt-injection defences;
  - rule-based claim extraction with a deterministic conflict predicate and selection rules;
  - value timelines;
  - Workflow Learning Lite (an event stream, a deterministic miner, versioned templates).
- **AWS:** the whole SAM stack, IAM roles, deployment, CloudWatch observability, and limits and
  throttling.
- **Quality:**
  - 343 API tests and 28 web unit tests;
  - 7 Playwright end-to-end tests in CI;
  - security acceptance tests run against the deployed stack;
  - an evaluation harness with golden sets, a 60-passage retrieval benchmark, and a workflow
    benchmark.
- **AI tools:** built with Claude Code (Claude Opus 5) and GitHub Copilot. Decisions are recorded as
  22 ADRs in the repository.
