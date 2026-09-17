# CROWN-X product requirements

## 1. Summary
CROWN-X is an evidence-first workspace for evolving project documents. It indexes a small set of
briefs, notes and announcements, answers questions across them with citations, detects where they
contradict each other, and shows how a value changed over time.

**Promise:** "Your project documents disagree. CROWN-X shows where, which source is newer, and why the
answer is supported."

## 2. Problem
Project facts (deadlines, owners, limits, requirements) change across document versions and informal
notes. Generic document chat answers from whichever passage it retrieves, and hides that another
source says something else. Teams find out late, and usually expensively.

## 3. Users
- **Primary:** student project and hackathon teams; early-stage engineering teams; developers juggling
  PRDs, meeting notes and requirements.
- **Secondary:** operations teams, researchers with evolving documents, small startups.

## 4. Jobs to be done
1. "Tell me the current value of this requirement."
2. "Show me whether my documents disagree."
3. "Show me exactly why you answered that."
4. "Show me what changed between versions."

## 5. Principles
- Evidence before eloquence: every claim has provenance, or it isn't made.
- Deterministic code before model inference, wherever the rule is known.
- Contradictions are surfaced, never silently resolved.
- The model explains evidence; it doesn't invent authoritative facts.
- The smallest useful scope, working end to end.

## 6. Example
Documents: *Project brief v1* says submissions close 20 Sept; *Organiser update* and *Meeting notes*
say 22 Sept. Question: "What is the current submission deadline?"

Response: "Sources disagree. Two newer sources say 22 September, one older source says 20 September.
Showing 22 September because those sources are newer. Check the evidence before relying on it." Each
value carries its source chips; the conflict inspector shows both passages side by side.

## 7. Scope

### P0: the hackathon MVP (M1-M4)
- Upload PDF, TXT, MD; extract and normalize; chunk with provenance (source, version, timestamp,
  page or section).
- Index and retrieve (OpenSearch), scoped per workspace.
- Evidence-grounded answers with citations and an explicit insufficient-evidence path.
- Deterministic contradiction detection for dates, numbers, categories, owners, requirements.
- Version-aware selection of the current value, with the rule stated.
- Timeline of value changes for a subject and attribute.
- Polished web UI (docs/UI_UX.md, docs/DESIGN.md); deployed on AWS.

### P0-stretch: Workflow Learning Lite (M5, only after M3 is verified)
CROWN-X records its own native events, detects repeated sequences deterministically, explains each
pattern with its event traces, and lets the user save or dismiss it as a workflow template. It never
executes a workflow. (ADR-005)

### P1: after the MVP is green
Human review state for conflicts; a read-only MCP server (`search_documents`, `find_conflicts`,
`get_timeline`, `explain_evidence`); a basic entity graph.

### Post-hackathon
Durable LangGraph orchestration, permissioned workflow execution, external connectors, temporal
memory, hybrid retrieval benchmark (Qdrant, reranking), MLflow and Langfuse evaluation, OpenTelemetry,
multi-tenant auth.

### Non-goals for the hackathon
Autonomous agents or desktop actions; sending email or editing external systems; universal knowledge
graph; unlimited file types; medical, legal or financial advice; claims of truth beyond indexed
evidence; enterprise IAM across organizations.

## 8. Success metrics
**Product:**
- time to first answer
- share of answers with evidence
- contradiction discovery on the seeded scenario
- demo path completed without rescue

**AI quality:** measured against `docs/EVALUATION.md`, never asserted:
- retrieval recall@k and evidence precision
- citation correctness
- groundedness
- contradiction precision and recall
- temporal selection accuracy

**Engineering:**
- p50 and p95 latency per stage
- ingestion failure rate
- error rate
- deploy success

Report measured values only. A target without a baseline isn't a result.

## 9. Differentiation
Not a PDF chatbot:
- contradictions are objects with evidence on both sides
- selection of the current value is explainable
- source chronology is visible
- every claim traces to a stored passage
