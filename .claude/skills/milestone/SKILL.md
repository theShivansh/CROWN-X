---
description: Plan and execute one CROWN-X milestone end to end, from its stage prompt to a verified commit, with scope control and state persistence.
argument-hint: "[M0|M1|M2|M3|M4|M5|M6]"
disable-model-invocation: true
---

# Milestone $ARGUMENTS

## Load the stage
The milestone's stage prompt is the brief for this session:

| Milestone | Stage prompt |
|---|---|
| M0 | `prompts/00-OPENING-BOOTSTRAP.md` |
| M1 | `prompts/01-M1-WALKING-SKELETON.md` |
| M2 | `prompts/02-M2-GROUNDED-ANSWERS.md` |
| M3 | `prompts/03-M3-CONTRADICTIONS.md` |
| M4 | `prompts/04-M4-TIMELINE-POLISH-RELIABILITY.md` |
| M5 | `prompts/05-M5-WORKFLOW-LEARNING-LITE.md` |
| M6 | `prompts/06-M6-FREEZE-AND-SUBMIT.md` |

Read that prompt in full, then everything it lists under "Read first". Also read the `$ARGUMENTS`
section of `docs/MILESTONES.md` and the current `docs/PROGRESS.md`. If the previous milestone's
done-means aren't met, say which item and stop: building on red costs more than fixing it first.

## Plan, in plan mode
Present:
- the smallest vertical slice that meets the done-means;
- the files and components that change;
- the decisions needing the user;
- the risks, each with the kill criterion that applies;
- how each done-means item will be observed, and at which level.

Wait for approval.

## Build
Follow the stage prompt. Keep the product runnable between slices, and commit each green slice by
explicit path. Load the domain skill when entering its area: `rag-evidence`, `crown-ui` or
`workflow-learning`. Ideas outside the milestone go to the Parking lot in `docs/PROGRESS.md`.

## Close
Run `/verify-stage $ARGUMENTS`, and record material decisions with `/record-decision`. Then do the
stage prompt's "Finish" section: ledger updates, commit and push, and the report it asks for.
