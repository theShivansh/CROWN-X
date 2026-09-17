---
description: Start a CROWN-X session from the ledger. Reads PROGRESS, the current milestone, recent decisions and the actual repo state, reconciles them, and states what happens next.
disable-model-invocation: true
---

# Resume

## Repo state right now

Recent commits:
!`git log --oneline -12`

Working tree:
!`git status --short`

## Do this

1. Read `docs/PROGRESS.md` in full, then the current milestone's section in `docs/MILESTONES.md`.
2. Read the index of `docs/DECISIONS.md` and the three newest entries.
3. Compare the ledger with the repo state above. Where they disagree, the repo wins: correct
   `docs/PROGRESS.md` first and say what you corrected.
4. Check the clock against `docs/HACKATHON.md`: which day of the event it is, and whether the
   current milestone is on schedule for its day. If it is behind, name the kill criterion that applies.
5. Report in at most eight lines:
   - current milestone and its status
   - what is done, at which verification level
   - the next concrete step
   - open blockers
   - files you expect to touch

Don't start implementing until that report is on screen. If a milestone is ready to begin, suggest
`/milestone <id>`.
