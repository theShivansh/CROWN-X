# 05 · M5 · Workflow Learning Lite (gated)

**Gate:** `docs/PROGRESS.md` must show M4 verified, with the golden path live. If it doesn't, stop
here, say so, and move to `prompts/06-M6-FREEZE-AND-SUBMIT.md`. This feature exists to add depth to a
product that already works. Built on top of a shaky golden path, it costs more in the video than it
adds (ADR-005).

If the gate passes: CROWN-X notices how a team's work in the product repeats, explains the pattern
with the exact events behind it, and offers to save it as a workflow. It never runs a workflow. The
engineering story for judges is that discovery is deterministic and reproducible, and the model only
names what code already found.

## Read first
- `CLAUDE.md`
- `.claude/skills/workflow-learning/SKILL.md`
- `docs/PRD.md` §7 (Workflow Learning Lite)
- `docs/SRS.md` (FR-WL, the workflow entities)
- `docs/ARCHITECTURE.md` §12
- `docs/UI_UX.md` §3.7
- `docs/EVALUATION.md` §6
- ADR-005 in `docs/DECISIONS.md`

## 1. Feature flag first
Add `WORKFLOWS_ENABLED` (SAM parameter, default `false`) and `NEXT_PUBLIC_WORKFLOWS_ENABLED`. With the
flags off, nothing in this milestone is reachable, logged or rendered. Everything below is built
behind them, so switching it off on Sunday costs one deploy and no code change.

## 2. Events
**Native events recorded:**
- `document_uploaded`
- `question_asked`
- `evidence_opened`
- `conflict_opened`
- `timeline_opened`
- `answer_copied`
- `workflow_saved`

The web client sends them to `POST /workspaces/{ws}/events` with a client-generated `event_id`
(UUIDv7), a timestamp and a minimal payload reference (IDs only, never document text).

**Server:**
- validates the event type against the enum;
- writes `EVENT#{ts}#{event_id}` with a conditional put, so retries are idempotent;
- attaches `session_id`: a new session when more than 30 minutes separate events in a workspace.

## 3. The miner (`domain/workflows.py`, pure and deterministic)
**Input:** the workspace's events and a config (minimum support default 3, n from 3 to 7, a 30-minute
session gap). **Output:** candidate sequences, each with:
- `sequence`;
- `support`, the number of sessions containing it as a contiguous run;
- `last_seen`;
- `confidence`, defined as support divided by the number of sessions containing the sequence's first
  event;
- `example_session_ids`, up to three.

**Rules:**
- Drop a candidate that's a sub-sequence of a longer candidate with equal support.
- Duplicated consecutive events of the same type collapse to one before mining, so double-clicks don't
  inflate support.
- Output order is fully specified (support descending, length descending, then lexicographic), so
  identical input gives byte-identical output.

`POST /workspaces/{ws}/workflow-suggestions:refresh` runs the miner and upserts suggestions;
`GET /workspaces/{ws}/workflow-suggestions` returns them. Save and dismiss are separate endpoints.
Saving writes a versioned template; dismissing hides that exact sequence until its support grows.

**Naming.** One Bedrock call per new suggestion, given only the event types and two example traces,
returns a short name and a one-sentence description. If the call fails, the suggestion shows the
sequence without a name. Nothing depends on the model's text.

## 4. UI (UI_UX §3.7)
Build with `prompts/07-UI-SCREEN-PASS.md`:
- **Suggestion card:** "Repeated workflow detected", 4-7 compact nodes, occurrences and last-seen
  badges, Save workflow / Dismiss, and "Why detected?".
- **Detail view:** ordered steps on the left; matching event traces with timestamps on the right; the
  saved version at the bottom.
- **Plain-language definitions:** confidence is shown as "seen in 3 of 4 sessions that started this
  way", never a bare percentage (CLAUDE.md rule 10).

## 5. Benchmark
`evals/workflows/generate.py` builds synthetic event traces with a fixed seed: true repeated
workflows, near-misses, reorderings, duplicates, unrelated interleavings and one-off sequences, each
labelled. `evals/workflows/run.py` reports pattern precision, recall, false-suggestion rate,
support-count accuracy and a determinism check. Record in `docs/BENCHMARKS.md`, and look through every
false suggestion by hand, noting the pattern.

## 6. A demo trace
Generate the demo workspace's workflow history by driving the real UI through the "prepare sprint
review" routine three times with Playwright MCP, so the suggestion comes from real events. Don't
insert events into the table.

## Tests this milestone needs
**Unit:**
- normalization and duplicate collapse;
- support counting across sessions;
- the sub-sequence rule;
- the confidence definition;
- determinism (same input twice gives identical serialized output);
- the session-gap boundary.

**API:**
- a retried event with the same `event_id` doesn't double count;
- with the flag off, every endpoint returns 404;
- cross-workspace access returns 404.

**Integration:** events, then refresh, then a suggestion, then save and dismiss, on the deployed stack.
**E2E (`@critical`):** the golden path still passes with the flag on.

## Kill criterion
Not live and verified by Sunday 10:00: turn the flags off, redeploy, confirm the golden path, and keep
the feature out of the video and writeup. Record the decision in PROGRESS.

## Done means
- [ ] Determinism, support and duplicate tests pass (unit)
- [ ] Events → refresh → suggestion → save and dismiss work end to end (integration)
- [ ] The suggestion card explains its events on the deployed URL (live)
- [ ] The golden path still passes, with the flag on (live)
- [ ] Workflow benchmark recorded, false suggestions reviewed

## Finish
- Update PROGRESS: the M5 row, flag state, next-session line, and verification log.
- Commit by path and push.
- Report: whether it ships in the video, the benchmark numbers as measured, and the flag state on the
  demo stack.
