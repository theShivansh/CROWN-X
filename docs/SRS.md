# CROWN-X software requirements

## 1. System boundary
Browser client · API layer (API Gateway + Lambda) · ingestion pipeline · retrieval layer · reasoning
layer (Bedrock) · contradiction engine · provenance formatter · persistence (S3, OpenSearch, DynamoDB).

## 2. Functional requirements
| ID | Requirement |
|---|---|
| FR-01 | Create a workspace and isolate every document, chunk, claim, conflict and event by `workspace_id`. |
| FR-02 | Accept PDF, TXT and Markdown through a signed upload flow; reject unsupported or oversized files with actionable errors. |
| FR-03 | Extract text and metadata; create bounded chunks with stable IDs; ingestion is idempotent by checksum. |
| FR-04 | Preserve filename, upload time, detected version label, source timestamp (when present), page or section, checksum. |
| FR-05 | Retrieve candidate chunks for a question using lexical and semantic signals with workspace and metadata filters; keep ranks and scores. |
| FR-06 | Return a structured answer whose every claim has evidence IDs, or an explicit insufficient-evidence answer. |
| FR-07 | Extract comparable claims and detect conflicts where subject and attribute match and normalized values differ; keep both claims and their evidence. |
| FR-08 | Select the current value by an explicit rule (source timestamp, then version label, then upload time) and state the rule; don't select when no rule applies. |
| FR-09 | Render chronological value changes for a subject and attribute, marking conflicts. |
| FR-10 | Record an audit event per request: request ID, workspace, document IDs, retrieval IDs, model invocation ID, outcome, latency, error. |
| FR-11 | Report processing stages per document and per query so the UI can name real work. |

### Workflow Learning Lite (M5, gated)
| ID | Requirement |
|---|---|
| FR-WL-01 | Record CROWN-native events in an append-only stream per workspace. |
| FR-WL-02 | Normalize equivalent events into stable event types. |
| FR-WL-03 | Detect repeated ordered sequences without a model call. |
| FR-WL-04 | Compute support, recency and confidence, each defined in the response. |
| FR-WL-05 | Explain each suggestion with representative event traces. |
| FR-WL-06 | Let the user save, rename or dismiss a suggestion. |
| FR-WL-07 | Persist saved workflows as versioned templates. |
| FR-WL-08 | Render a workflow as an ordered list or DAG. |

## 3. API contract (all JSON; request and response schemas versioned and validated with Pydantic)
| Method and path | Purpose |
|---|---|
| `GET /health` | Liveness plus dependency checks (S3, OpenSearch, DynamoDB, Bedrock config). |
| `POST /workspaces` | Create a workspace. |
| `POST /workspaces/{ws}/documents/upload-url` | Pre-signed S3 POST for one file, with a `content-length-range` condition so S3 enforces the size limit; returns `document_id`. |
| `POST /workspaces/{ws}/documents/{doc}/complete` | Confirm the object (size, type, checksum); return the existing document on a duplicate checksum; otherwise invoke ingestion asynchronously. |
| `GET /workspaces/{ws}/documents` | Documents with status and stage. |
| `POST /workspaces/{ws}/query` | Stage 1: retrieve evidence and relevant conflicts; persist a query record; return `query_id`. Body: `question`, optional `document_ids`. |
| `POST /workspaces/{ws}/queries/{query_id}/answer` | Stage 2: grounded answer over the evidence stored on the query record (no re-retrieval). No model call when there is no evidence. (ADR-009) |
| `GET /workspaces/{ws}/conflicts` | Detected conflicts. |
| `GET /workspaces/{ws}/timeline?subject=&attribute=` | Value history. |
| `POST /workspaces/{ws}/events` | Record a native event (M5). |
| `POST /workspaces/{ws}/events` | A UI event from the browser: UUIDv7 `event_id`, a client event type, IDs only (M5, ADR-022). |
| `POST /workspaces/{ws}/workflow-suggestions/refresh` | Run the deterministic miner, name new suggestions once, return them (M5; `/refresh`, not `:refresh`, ADR-022). |
| `GET /workspaces/{ws}/workflow-suggestions` | Suggestions (M5). |
| `POST /workspaces/{ws}/workflow-suggestions/{id}/save`, `/dismiss` | Act on a suggestion (M5). |

Stage 1 (`/query`) returns `query_id`, `status` (`insufficient_evidence` when nothing relevant is
retrieved, otherwise `retrieved`), `evidence` and `conflicts`. Stage 2 (`/answer`) returns the full
shape below. Together they form one question's result:
```json
{
  "request_id": "req_…",
  "status": "grounded | conflict | partial | insufficient_evidence",
  "answer": "…",
  "claims": [{"text": "…", "evidence_ids": ["ev_…"]}],
  "evidence": [{"evidence_id": "ev_…", "document_id": "doc_…", "chunk_id": "ch_…",
                "quoted_span": "…", "page_or_section": "…", "source_timestamp": "…",
                "version_label": "…", "retrieval_rank": 1}],
  "conflicts": [{"conflict_id": "cf_…", "type": "date", "subject": "submission",
                 "attribute": "deadline", "claim_a": {…}, "claim_b": {…},
                 "selected_claim_id": "cl_…", "selection_rule": "newest_source_timestamp"}],
  "timeline_ref": {"subject": "submission", "attribute": "deadline"}
}
```

## 4. Data model
- **Workspace:** `workspace_id`, `name`, `created_at`
- **Document:** `document_id`, `workspace_id`, `filename`, `content_type`, `checksum`, `uploaded_at`,
  `version_label`, `source_timestamp`, `source_uri`, `status`, `stage`, `error`
- **Chunk:** `chunk_id`, `document_id`, `workspace_id`, `text`, `page_or_section`, `char_start`,
  `char_end`, `embedding_ref`, `metadata`
- **Evidence:** `evidence_id`, `chunk_id`, `quoted_span`, `retrieval_rank`, `retrieval_score`,
  `citation_label`
- **Claim:** `claim_id`, `workspace_id`, `subject`, `attribute`, `raw_value`, `normalized_value`,
  `unit`, `source_chunk_id`, `source_timestamp`, `extraction_method` (`rule` | `model`). Since M3
  (ADR-020) it also carries:
  - `document_id`, `filename`, `version_label`, `uploaded_at`;
  - `quote`, with its offsets `char_start`/`char_end` and the value's `value_start`/`value_end`;
  - `trigger` and `trigger_is_label`;
  - `confidence.extraction` (0-1, defined in ADR-020, never shown as a number).
- **Conflict:** `conflict_id`, `workspace_id`, `claim_a`, `claim_b`, `type`, `severity`, `status`,
  `selected_claim_id`, `selection_rule`.
  - It is derived from the claims whenever it's read, never stored (ADR-020).
  - The ID is a hash of the two sorted claim IDs.
  - The API groups the pairs by key, with the key's claims oldest first (the inspector's timeline)
    and `primary_conflict_id`.
- **AuditEvent:** `event_id`, `request_id`, `workspace_id`, `event_type`, `timestamp`, `status`,
  `latency_ms`, `model_invocation_id`, `retrieval_ids`
- **WorkflowEvent (M5):** `event_id`, `workspace_id`, `event_type`, `occurred_at` (server time),
  `attributes` (IDs only; `client_at` for browser events). `session_id` is derived when mining
  (ADR-022).
- **WorkflowSuggestion (M5):** `suggestion_id`, `steps[]`, `support`, `recency`, `confidence`,
  `first_step_count`, `traces[]`, `trace_sessions[]`, `trace_times[]`, `example_session_ids[]`,
  `name`, `description`, `named_by`, `saved_versions[]`. Dismissal is stored as
  `dismissed_at_support`.
- **WorkflowTemplate (M5):** `suggestion_id`, `version`, `name`, `description`, `steps[]`, `support`,
  `source_event_ids[]`, `saved_at`, `automation: "none"`. Versions are immutable.

## 5. Non-functional requirements
- **Reliability:** timeouts on every external call; retries only for idempotent operations, bounded;
  idempotent ingestion; partial failure reported, never hidden; no silent fallbacks.
- **Security:** workspace isolation in the query; least-privilege IAM; server-side validation; no
  secrets in code, prompts or logs; read-only tools by default. See `docs/SECURITY.md`.
- **Performance:** measure p50 and p95 separately for upload, ingestion, retrieval, generation and
  end to end. Report measurements; don't promise numbers.
- **Observability:** structured JSON logs with `request_id`; CloudWatch metrics per stage.
- **Determinism:** conflict detection and workflow mining give identical output for identical input
  and config.

## 6. Error handling
| Case | Response |
|---|---|
| Unsupported type | 400, the supported types listed |
| Over the size limit | 413, the limit stated |
| Empty extraction (scanned PDF) | 422, "no text found; upload a text PDF" |
| Duplicate upload | 200, the existing `document_id` |
| Retrieval unavailable | 503 degraded response stating that evidence could not be retrieved |
| Model timeout | one retry if safe, then 504 with `request_id` |
| No evidence | 200, `status: insufficient_evidence`, no fabricated value |
| Cross-workspace ID | 404, same as not found (no existence leak) |

## 7. Acceptance criteria (MVP complete)
A fresh deployment can:
1. ingest at least three seeded documents;
2. answer the seeded question with evidence that opens to the passage;
3. detect the seeded contradiction;
4. show both values with their sources and the selection rule;
5. render the timeline;
6. do all of it on the deployed AWS URL, with the AWS path visible in the recorded demo.
