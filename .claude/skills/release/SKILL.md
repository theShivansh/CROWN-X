---
description: Freeze and submit CROWN-X for First Commit 2026. Runs the submission checklist, drafts the writeup, checks the video script against the judging criteria, and verifies the public repo. Invoke manually on the final day.
disable-model-invocation: true
---

# Release

The full brief for this day is `prompts/06-M6-FREEZE-AND-SUBMIT.md`; this skill is its checklist.
Source of truth: `docs/HACKATHON.md` (rules verified 2026-09-16, judging criteria, video script,
submission checklist).

## 1. Freeze
- No new features. Only fixes for failures found below.
- `/verify-stage M6`, all gates. The golden demo passes live on the deployed URL, driven through Playwright MCP.
- Eval run recorded in `docs/BENCHMARKS.md` with commit and date. No `TBD` numbers remain in anything
  that will be published; unmeasured values say "not measured".

## 2. Repository
- Public, default branch has the final commit, history starts inside the event window.
- README: problem, who it's for, demo GIF or screenshots, architecture diagram, AWS services and why
  each, setup and demo steps, limitations, credits.
- `CREDITS.md` names every AI coding tool used (required by the rules), every third-party
  component with its licence, and the pinned design skills.
- No secrets: gitleaks passed in CI on the final commit.

## 3. Writeup (draft into `docs/WRITEUP.md`)
Problem, who has it, what was built, where AWS fits (each service and the decision behind it,
including cost), what was hard, what's next. Plain claims only, each shown in the video or repo.

## 4. Video (three minutes or less)
Check the script in `docs/HACKATHON.md` against the criteria: idea, built on AWS, execution, demo.
Every claimed feature must appear on screen. End on the conflict evidence UI.

## 5. Submit early
Submit through the event form as soon as sections 1-4 pass, then improve only until the deadline.
Report exactly what was submitted and when.
