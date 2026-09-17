---
description: Build or change CROWN-X Workflow Learning Lite, which records native events, mines repeated sequences deterministically and suggests saveable workflows. Use for the event schema, sequence miner, suggestion API or workflow UI. Only after milestone M3 is verified.
---

# Workflow Learning Lite

Specs: `docs/PRD.md` (Workflow Learning Lite), `docs/SRS.md` (FR-WL, NFR-WL),
`docs/ARCHITECTURE.md` (Workflow Learning Lite), ADR-005.

## Gate first
Check `docs/PROGRESS.md`: M3 (contradictions) must be verified. If it isn't, stop and say so. This
feature is cut before it can endanger the core demo (ADR-005).

## Constraints
- CROWN-native events only (upload, ask, open evidence, open conflict, open timeline, save view).
  No external SaaS, no browser automation, and no execution of workflows.
- Append-only event stream in DynamoDB, idempotent by `event_id`, scoped by `workspace_id`.
- Discovery is deterministic: normalize event types, build sessions (gap > 30 min starts a new one),
  count ordered contiguous n-grams (n = 3..7), then keep candidates with support at or above the
  configured minimum (default 3) that aren't sub-sequences of an equally supported longer one.
- Scores: `support` (occurrences), `recency` (last seen), `confidence = support / sessions containing
  the first event`. Define each in the API response; never show an unexplained percentage.
- A model may only name and describe an already-detected sequence, with the event traces as input.
  Identical inputs and config give identical suggestions (NFR-WL-02).

## Tests
- normalization maps equivalents to one type
- repeated sequence found with the right support; one-off sequences ignored
- reordered and interleaved near-misses behave as documented
- duplicate events don't inflate support
- determinism: same input twice gives byte-identical suggestions
- integration: events, then candidate, then persisted suggestion, then save and dismiss
- every suggestion links to concrete source event IDs

Record an ADR when the algorithm, thresholds or event schema change.
