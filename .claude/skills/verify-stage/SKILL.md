---
description: Record a CROWN-X milestone's done-means and stage gates as PASS, FAIL or NOT TESTED with the evidence observed. Use before marking any milestone done.
argument-hint: "[M1|M2|M3|M4|M5|M6]"
---

# Verify $ARGUMENTS

This is the ledger entry for what was actually observed, so the next session and the writeup can
trust it. Evidence from this session counts if no relevant code changed since it was observed. Run a
check only when there's no such evidence yet.

## Gates, in order
Stop at the first gate that fails and report it; later gates are NOT TESTED.

1. **Scope:** the diff since the milestone started contains only milestone work.
2. **Functional:** each done-means item for `$ARGUMENTS` in `docs/MILESTONES.md` (and its stage prompt),
   at the level it names:
   - `unit`: the test run and its result;
   - `integration`: the real service's response or log line;
   - `live`: the deployed URL, driven through Playwright MCP. An HTTP 200 alone isn't a UI check.
3. **Quality:** lint, typecheck and the full test suites (commands in CLAUDE.md).
4. **Evaluation:** if retrieval, prompts, claims or conflicts changed, the eval run compared with the
   gates and the previous baseline in `docs/BENCHMARKS.md`.
5. **Security:** if endpoints, IAM, uploads, prompts or logging changed, the relevant acceptance tests
   in `docs/SECURITY.md`.
6. **Observability:** a failed request can be found by `request_id`.
7. **Docs:** CLAUDE.md commands, SRS and ARCHITECTURE match the code.
8. **Demo (M3 onwards):** the golden path runs without a manual step.

## Record
Append one line to the Verification log in `docs/PROGRESS.md`:
`YYYY-MM-DD HH:MM | $ARGUMENTS | commit | gates | level reached | failures`

Report a table (item | PASS / FAIL / NOT TESTED | evidence), and the smallest fix for each FAIL. A
milestone is done only when every done-means item passes.
