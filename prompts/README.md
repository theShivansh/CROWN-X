# Stage prompts

One prompt per stage of the build. Each gives Claude the goal, the context and constraints behind it,
the contracts that later stages depend on, and what counts as done. Paste the prompt at the start of
its session, or run `/milestone <id>`, which loads the same file.

## Run order

| # | Prompt | When | Milestone |
|---|---|---|---|
| 0 | `00-OPENING-BOOTSTRAP.md` | Thu, first hour after opening | M0 close-out, harness live, M1 planned |
| 1 | `01-M1-WALKING-SKELETON.md` | Thu | M1 |
| 2 | `02-M2-GROUNDED-ANSWERS.md` | Thu night to Fri morning | M2 |
| 3 | `03-M3-CONTRADICTIONS.md` | Fri | M3 |
| 4 | `04-M4-TIMELINE-POLISH-RELIABILITY.md` | Sat | M4 |
| 5 | `05-M5-WORKFLOW-LEARNING-LITE.md` | Sat night, only if M4 is verified | M5 |
| 6 | `06-M6-FREEZE-AND-SUBMIT.md` | Sun | M6 |

Inserts, used when needed rather than in sequence:

| Prompt | Use it when |
|---|---|
| `07-UI-SCREEN-PASS.md` | Building or polishing one screen properly. Repeatable, one screen per run. |
| `08-TRIAGE-BEHIND-SCHEDULE.md` | A gate fails, the clock slips, or deployment is blocked. |

## Per-session loop

```text
/resume                       reconcile the ledger with the repo
/milestone M2                 loads prompts/02-..., plans in plan mode, waits for approval
(build)                       the prompt's done-means are the finish line
/verify-stage M2              record evidence per done-means item
```

Before a session ends or context is compacted: update `docs/PROGRESS.md` and commit by path. Use
`/compact` rather than letting a long session run into the limit; the ledger carries the state across.

## How these prompts are written, and how to add to them
They follow current guidance for Claude Opus 5:
- They state goals, context, reasons and success criteria, and trust the model's own plan. Numbered
  steps appear only where order genuinely matters (deploys, git, submission).
- Constraints are stated once, plainly, with the reason beside them; no capital-letter emphasis.
- There are no "double-check your work" or "use a subagent to verify" lines. Opus 5 verifies its own
  work, and those instructions make it over-verify. The done-means say *what* must be observed.
- Working style (scope, delegation, how to report) lives once in `CLAUDE.md`, not in every prompt.

If you edit a prompt mid-event, change the requirement, not the volume. If Claude drifts, add the
missing context or reason rather than an "IMPORTANT".
