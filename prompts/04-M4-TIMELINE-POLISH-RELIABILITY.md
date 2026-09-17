# 04 · M4 · Timeline, polish and reliability

Make the golden path judge-ready. By the end of Saturday, the deployed product runs the whole demo
without a rescue step and shows the value history. It handles every state a real user could reach,
moves exactly where motion explains something, and a failure on camera would be diagnosable from
CloudWatch in under a minute.

This is the milestone where it's tempting to widen scope. The rule for today: anything that doesn't
make the three-minute video clearer, or the golden path more reliable, goes to the Parking lot.

## Read first
- `CLAUDE.md`
- `docs/MILESTONES.md` (M4)
- `docs/UI_UX.md` and `docs/DESIGN.md` (all)
- `.claude/skills/crown-ui/SKILL.md`, `references/COMPONENTS.md` and `references/ANTI_SLOP.md`
- `docs/SECURITY.md` (all), `docs/ARCHITECTURE.md` §§6, 10
- `docs/HACKATHON.md` §4 (the video script)
- `docs/PROGRESS.md`, for the state M3 left

Watch or read notes on Friday's rough recording, if the user shares them: its weak spots are today's
priorities.

## 1. Timeline
**API:** `GET /workspaces/{ws}/timeline?subject=&attribute=` returns the key's claims ordered by the
same signals the selection rule uses (source timestamp, then version order, then upload). Each event
has:
- date or ordering label;
- document name and version;
- raw and normalized value;
- `changed: bool` relative to the previous event;
- the conflict IDs it participates in.

Undated documents appear in their upload position, marked as such.

**UI** (UI_UX §3.6):
- a horizontal track;
- a marker at each value change;
- conflicting segments outlined with `--conflict`;
- events focusable, with arrow keys moving between them;
- below 1024px wide, a vertical list.

It's reachable from the conflict inspector and from the evidence panel. Build it with
`prompts/07-UI-SCREEN-PASS.md`.

## 2. Every state, and the signature sequence
Build out UI_UX §3 completely: the workspace empty state, ingestion card states including duplicates
and failures, all answer card states, and error states carrying `request_id` with a Retry that works.

Then the one signature sequence (DESIGN §6), bound to the real two-call query:
- evidence cards enter in rank order as call one returns;
- the conflict card appears between its two sources, with the beam running while the comparison stage
  is shown;
- the answer settles as call two returns, with citation chips linking to their cards.

Nothing else on the page moves. With `prefers-reduced-motion`, everything appears in its final state
immediately.

Add from COMPONENTS.md, adapted per its checklist:
- `search-modal`: the ⌘K / Ctrl+K "Ask CROWN" palette, with recent questions and conflicts to jump to;
- `animated-number`: the header counters, animating on change only.

A landing page (UI_UX §3.8) is allowed only once every done-means item below passes.

## 3. Reliability
- **Limits enforced server-side**, with SRS errors: max upload bytes, documents per workspace, and
  questions per workspace per hour, counted in DynamoDB with a TTL.
- **API Gateway throttling** on the routes, and reserved concurrency on the query and answer paths so
  a spike can't exhaust the account.
- **Latency per stage:** record upload URL, ingestion stages, retrieval, answer call and end to end as
  structured log fields (or Powertools Metrics). Save the CloudWatch Logs Insights queries that give
  p50 and p95 per stage in `docs/ARCHITECTURE.md`, and run them once to get today's numbers into
  `docs/BENCHMARKS.md`.
- **Failure paths, exercised on the deployed stack:**
  - an unsupported file;
  - an oversize file, refused by S3's content-length condition;
  - a scanned (textless) PDF;
  - a question with no evidence;
  - the answer model timing out. Simulate with a test-only config that shortens the timeout on a dev
    stack, never in the demo stack.

  Each shows its designed UI state and logs with `request_id`.
- **Diagnosis drill:** trigger an error on the deployed URL, copy the `request_id` from the UI, and
  find the full request in CloudWatch. Note the steps in `docs/ARCHITECTURE.md`; the video uses this.

## 4. Security acceptance
Automate the SECURITY §2 acceptance tests that can run against a deployed stack: T1 injection, T2
cross-workspace, T3 bad uploads, T5 log canary, T6 unretrieved citation, T7 limits. Put them in
`services/api/tests/integration/`, marked so CI can skip them without `EVAL_API_URL`. Review the SAM
template's IAM statements against T4 yourself: no `*` actions or resources without an ADR.

## 5. End-to-end tests
Playwright tests in `apps/web/e2e/`, tagged `@critical`, for the golden path and the main failure
states. In CI they run against the built static site, with the API mocked through `page.route`
fixtures recorded from real responses, so CI is deterministic. The same tests run against the
deployed URL when `E2E_BASE_URL` is set; run that once today.

## 6. Verify in the browser, in this session
Walk the golden path on the deployed URL with Playwright MCP:
- at 1440x900 and 1024x768;
- keyboard only;
- with reduced motion emulated.

Check the pre-delivery checklist in `ANTI_SLOP.md` §6 as you go, and fix what fails. If the user asks
for an independent pass before recording, that's what the `ui-verifier` agent is for.

## Out of scope
Workflow learning, new conflict types, light theme, auth beyond the workspace ID, and any feature not
in the video script.

## Done means
- [ ] Timeline shows the deadline changing with the conflict marked (live)
- [ ] Every UI_UX §3 state reachable and designed; ANTI_SLOP §6 checklist passes at 1440 and 1024,
  keyboard-only and with reduced motion (live)
- [ ] A failed request traced in CloudWatch by `request_id`; Logs Insights queries saved (integration)
- [ ] Security acceptance tests T1-T3, T5-T7 pass against the deployed stack; IAM reviewed for T4
  (integration)
- [ ] `@critical` Playwright tests pass in CI and once against the deployed URL
- [ ] Golden path runs start to finish on the deployed URL without a manual step (live)
- [ ] p50 and p95 per stage recorded in BENCHMARKS

## Kill criterion
After 18:00 Saturday, any polish item that puts the golden path at risk is dropped, not finished.
Whether M5 happens is decided at the end of this milestone: only if every done-means item above passed.

## Finish
- Update PROGRESS: the M4 row, the M5 decision with its reason, the next-session line, and the
  verification log.
- Commit by path and push.
- Report:
  - the live URL;
  - done-means results;
  - latency numbers as measured;
  - the M5 go or no-go;
  - the two things most likely to go wrong during recording.
