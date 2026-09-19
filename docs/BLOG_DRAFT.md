# Draft: AWS Builder Center post

> Not yet published. To be posted by the author on AWS Builder Center; add the link to
> `docs/SUBMISSION.md` ("Blog links") once it's live. About 1,300 words. Every number is from
> `docs/BENCHMARKS.md`.

**Suggested tags:** Amazon OpenSearch Service, AWS Lambda, Amazon DynamoDB, AWS Amplify, Generative AI,
RAG, Serverless

---

# My chatbot was confidently wrong about our deadline, so I built one that shows where documents disagree

*What I learned building CROWN-X, an evidence-first document assistant, on AWS in four days for AWS
First Commit 2026.*

![CROWN-X answering "What is the current submission deadline?": sources disagree, 22 Sep chosen by the newest source date](https://raw.githubusercontent.com/theShivansh/CROWN-X/main/docs/media/demo-hero.gif)

## The problem: facts change, chatbots don't notice
Every student project I've been on keeps its facts in a pile of versions: the original brief, a
revised spec, an organiser's email, and notes pasted from the team chat. The brief says submissions
close on **20 September**. The organiser's update moves it to **22 September**. The meeting notes
confirm 22.

Ask a typical retrieval-augmented chatbot "When is the deadline?" and it answers from whichever
passage ranked first. It sounds sure of itself, and it never mentions that another source says
something else. You find out when it's too late.

So I set myself three rules for **CROWN-X**:
1. **Evidence or nothing.** Every sentence cites a stored passage, or the answer says "Not enough
   evidence".
2. **Code decides conflicts.** A model may help extract facts. It never decides that two values
   disagree.
3. **Documents are data.** Nothing inside an uploaded file can change the instructions.

Try it: [the live app](https://main.d1jy52bqj8dt1h.amplifyapp.com/) ·
[the code](https://github.com/theShivansh/CROWN-X).

## The architecture: small, serverless, and all in ap-south-1

![Architecture](https://raw.githubusercontent.com/theShivansh/CROWN-X/main/docs/media/architecture-overview.svg)

The whole backend is one AWS SAM template:
- **AWS Amplify Hosting** serves a static Next.js export.
- **Amazon API Gateway (HTTP API)** is the edge. Its per-route throttles double as a cost control:
  the answer route allows 1 request per second.
- **AWS Lambda** runs two functions, the API and the ingestion worker, each with its own
  least-privilege IAM role.
- **Amazon S3** takes uploads straight from the browser through a size-limited pre-signed POST, so no
  file bytes ever pass through Lambda.
- **Amazon OpenSearch Service** holds one index for both BM25 and k-NN search.
- **Amazon DynamoDB** holds documents, extracted claims, the audit trail, workflow events and
  hourly quota counters, which expire with TTL.
- **Amazon CloudWatch** gets a request ID and per-stage timings on every log line.

A question is **two calls**. `POST /query` embeds the question, runs BM25 and k-NN with the workspace
filter *inside* each OpenSearch query, fuses the two rankings with reciprocal rank fusion, and stores
the top 8 passages. It also runs the conflict check, in plain code, before any model is involved.
Then `POST /answer` sends exactly those stored passages to the model as an escaped data block, and
code validates every citation in what comes back.

Inside Lambda, retrieval takes **39 ms at p50 and 65 ms at p95**. The answer call takes 731 ms and
1153 ms.

## Day one: Bedrock said no, so I built a switch
My plan was Amazon Bedrock for both answers and embeddings. On day one, my brand-new AWS account could
*list* Bedrock models, but every inference call was denied while AWS verified the account.

Instead of waiting, I put the answer model and the embedder behind one provider interface:
- **Answers** come from `gpt-oss-120b` on Groq, falling back once to `gpt-oss-20b`. The key is a
  SecureString in **SSM Parameter Store**.
- **Embeddings** come from `bge-small-en-v1.5`, quantized to int8 and run with **onnxruntime inside
  the Lambda**. That's 4 ms per question, and indexing costs no model calls at all.
- **Bedrock** is still a configuration switch away.

**Lesson 1:** check model access with a real call on day one. Listing models proves nothing.

## The part I'm proudest of: conflicts decided by code
At ingestion, rules extract typed **claims**: a trigger phrase ("submissions close on") plus a date,
number or owner in the same sentence. Each value is normalized, so "22 Sept" becomes 2026-09-22 and
"60 rpm" becomes "60 requests per minute".

Two claims **conflict** only when all of these hold:
- the same fact and the same type;
- both normalized, with the same unit;
- different documents;
- different values.

The current value is then chosen by a written rule: the newest source date, then version order, then
the latest upload. The UI names the latest upload as the weakest rule.

![Conflict inspector](https://raw.githubusercontent.com/theShivansh/CROWN-X/main/docs/media/conflict-inspector.png)

On the demo scenario, contradiction precision and recall are both **1.0**, offline and on the deployed
stack. Values that differ only in format were never flagged.

My first version got something important wrong. It attached a conflict whenever a conflicting passage
was *retrieved*. With top-8 retrieval over a small workspace, nearly every question showed a conflict
card, and status accuracy fell from 0.825 to 0.275. Now a conflict also needs the question to name
the fact. The system can miss a conflict, but it never invents one.

**Lesson 2:** detecting a conflict and deciding whether it matters to this question are two separate
problems.

## Measuring retrieval honestly
I wrote a 60-passage, 30-query benchmark with passage-level labels and froze it before the first
run. It includes paraphrases, Hinglish questions, vague "what if" questions, and hard negatives
(passages that share the words but don't answer the question).

![Recall](https://raw.githubusercontent.com/theShivansh/CROWN-X/main/docs/media/benchmark-chart-recall.svg)

Production hybrid retrieval reached **recall@8 of 0.95** on the deployed stack. Recall@8 is the number
that matters here, because the model reads all 8 passages.

A cross-encoder reranker lifted MRR from 0.694 to 0.864 offline, but it added more latency than the
+150 ms p95 gate I had set in advance, and it didn't change recall@8. So it's built, measured and
**off**.

Then my own guardrails bit me. The first live benchmark run at the freeze silently lost 19 of 63
queries to the throttles and hourly quota I had added the day before, and the printed table didn't
show it. I threw those numbers away, made the harness pace itself and fail on any error, and reran.

**Lesson 3:** a benchmark that hides its errors is worse than no benchmark.

## Workflow learning, without letting the model drive
CROWN-X also records what a team does (ask, inspect a conflict, open the timeline, copy the answer)
as events that hold IDs only. A deterministic miner finds step sequences that repeat, and shows them
as a suggestion with the exact events behind it, for example "Finished 3 of the 12 times it started
this way". It never shows a bare percentage. The model's only job is to suggest a name. Nothing runs
automatically.

The first benchmark run scored precision **0.4**: fragments of real workflows outranked the workflows
themselves. A "fragment rule", which keeps a sub-sequence only if it also happened often enough on its
own, brought precision to **1.0** on the synthetic benchmark.

I also hit a clock bug: ordering browser events by the browser's clock scrambled sequences. The
server's clock now orders everything, and retries are deduplicated by event ID.

## Cost, and keeping it bounded
My account's Lambda concurrency limit was 10, so reserved concurrency wasn't possible. Instead:
- **per-route throttles** in API Gateway;
- **60 questions per workspace per hour**, counted with an atomic DynamoDB `ADD` *before* any
  embedding, search or model call;
- **one model call per question**, and none when no evidence is found.

AWS Cost Explorer reported **$1.86** of usage for the three days, all covered by credits. $1.75 of that
was the single OpenSearch node, which runs all the time.

## Observability that works on camera
Every error card in the UI shows a request ID. Every log line carries it, along with the time each
stage took. A saved Logs Insights query finds a failed request in about five seconds.

One surprise: the standard-library INFO lines my tests captured never reached CloudWatch. Only the
Powertools logger's lines did.

**Lesson 4:** a log line in a test isn't a log line in CloudWatch.

## What's next
- Claim extraction for free-text facts. A model may extract them, but still never decides a conflict.
- Accounts with Amazon Cognito.
- Weighted fusion, tuned on a separate development set.
- Bedrock as the production answer model.

## Built with
- AWS: Amplify, API Gateway, Lambda, S3, OpenSearch Service, DynamoDB, CloudWatch, SSM, SAM.
- Groq for the answer model.
- Written with **Claude Code (Claude Opus 5)** and **GitHub Copilot**.

The code, 22 architecture decision records and every benchmark are on
[GitHub](https://github.com/theShivansh/CROWN-X).
