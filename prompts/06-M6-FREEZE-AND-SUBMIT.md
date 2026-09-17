# 06 · M6 · Freeze and submit

Today ends with a scored submission. The rules score only what is submitted: a public repository, a
video of three minutes or less, and a writeup. A late submission isn't scored, whatever the reason. So
the order of today is **submit something complete early, then improve it**. The work is freezing
features, proving what's there, telling the story honestly, and getting the form in with hours to
spare.

Some steps only the user can do: recording and uploading the video, submitting the form, publishing
a blog. Prepare everything those steps need, down to the exact text to paste, and say plainly when it's
the user's turn.

## Read first
`CLAUDE.md`, `docs/HACKATHON.md` (all), `.claude/skills/release/SKILL.md`, `docs/PROGRESS.md` (the
deadline and every milestone's state), `docs/BENCHMARKS.md`, `docs/DECISIONS.md` (index),
`CREDITS.md`.

## Timeline for the day
Work backwards from the deadline recorded in PROGRESS, and write the schedule there first:

| Target | Step |
|---|---|
| Deadline minus 8h | Feature freeze in place, final eval run done |
| Deadline minus 6h | Repository, README, credits and writeup complete |
| Deadline minus 5h | Video recorded |
| Deadline minus 4h | **Submitted** |
| After that | Fixes only, with a resubmission if the form allows edits |

## 1. Freeze
- Tag the freeze commit (`git tag freeze-1`); every change after it is a fix, recorded in PROGRESS with
  its reason.
- M5: confirm the flag state decided yesterday. If workflows are off, confirm they are unreachable on
  the deployed site.
- Run the final eval against the deployed stack. Record it in `docs/BENCHMARKS.md` with command,
  dataset version, commit and date. Any metric that wasn't measured says "not measured". No number
  anywhere in the repository, README, writeup or video comes from anything else.
- `/verify-stage M6`: all gates, with the golden path live on the deployed URL at 1440x900 and
  1024x768.

## 2. Repository
Rewrite `README.md` as the product README; move the kit's "Working with Claude Code" section below
it:
1. What CROWN-X is, in two sentences, and who it's for.
2. A screenshot or short GIF of the conflict inspector, captured from the deployed site with
   Playwright MCP.
3. **Try it:** the deployed URL and the demo workspace link.
4. **How it works:** the evidence pipeline and the deterministic conflict predicate, in a paragraph
   each.
5. **Architecture:** the mermaid diagram from ARCHITECTURE §2 (GitHub renders it); each AWS service
   with its reason; the cost guardrails.
6. **Measured results:** the BENCHMARKS table as it stands.
7. **Run it locally:** exact commands, taken from CLAUDE.md.
8. **Limitations**, stated plainly: auth is a workspace ID; supported conflict types; English only;
   anything cut.
9. **Credits and AI tools:** link `CREDITS.md`.

Then:
- `CREDITS.md`: every installed third-party component with commit and licence, fonts, icons, the design
  skills, and every AI tool used. The rules require naming AI coding tools.
- Confirm the repository is public, the default branch holds the freeze commit, CI is green on it,
  gitleaks passes, and the history starts inside the event window.

## 3. Writeup
Draft `docs/WRITEUP.md` in the event's structure (HACKATHON §5):
- the problem and who has it;
- what was built;
- how it works;
- where AWS fits, with each service, the decision behind it and the cost reasoning, since that is what
  "Built on AWS" is scored on;
- what was hard;
- limitations;
- what's next;
- AI coding tools used;
- credits.

Every claim must be visible in the video or verifiable in the repository. Match its length to the
form's fields and limits; ask the user to paste those limits if you can't read the form. Where the form
has separate fields, produce the text for each field.

## 4. Video
Prepare what the user needs to record it in one or two takes:
- **Take sheet** (`docs/VIDEO_TAKE_SHEET.md`):
  - the script from HACKATHON §4 with exact on-screen actions and the words to say, timed to three
    minutes or less;
  - browser zoom and window size;
  - which workspace and question to use;
  - what to have open in other tabs: the architecture diagram, the CloudWatch log line for the request
    made on camera, and the BENCHMARKS table.
- **Pre-flight on the deployed site,** immediately before recording:
  - the demo workspace is clean and ingested;
  - the golden question returns the conflict;
  - reduced motion is off;
  - no console errors;
  - the diagnosis drill works.
- After the user records, check the video against the judging criteria (idea, built on AWS, execution,
  demo): every claimed feature appears on screen, AWS is visibly used, and it's three minutes or less.
  List specific retakes if any are needed.

## 5. Submit
Prepare a submission sheet with every form field's text, the repository URL, the deployed URL, the
video link once uploaded, and the writeup. The user submits it. Record in PROGRESS the time of
submission and what was submitted.

## 6. After submission
- Fixes only, each a small commit with the reason, and only if it doesn't put the deployed golden path
  at risk.
- Optional, if time allows:
  - a Best Blog draft for AWS Builder Center (`docs/BLOG_DRAFT.md`, built from the writeup and ADRs);
  - a Build It submission, if the stack also runs locally on SAM Local.
- Don't tear anything down: judges may open the URL. `/aws-ship teardown` is for after results.

## Out of scope
New features, refactors, dependency upgrades, and anything the video doesn't show.

## Done means
- [ ] Freeze tagged; final eval recorded; `/verify-stage M6` passes live
- [ ] README, CREDITS and WRITEUP complete; repository public; CI and gitleaks green on the submitted
  commit
- [ ] Take sheet ready; video recorded and checked against the criteria
- [ ] Submitted; time and contents recorded in PROGRESS

## Finish
- Update PROGRESS: the M6 row, what was submitted and when, and post-submission fixes.
- Commit by path and push.
- Report: the submission time, the links submitted, anything still at risk, and the teardown reminder
  for after results.
