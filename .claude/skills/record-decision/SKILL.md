---
description: Record a material CROWN-X decision (architecture, data model, AWS service, AI behaviour, security, UI direction or scope) as an ADR in docs/DECISIONS.md. Use when a choice would surprise someone reading the code later, or reverses an earlier entry.
argument-hint: "[short title]"
---

# Record decision: $ARGUMENTS

1. Read the index of `docs/DECISIONS.md`. If an entry already covers this, update it (and its
   status) instead of adding a duplicate. If this reverses an entry, mark that one `superseded by
   ADR-NNN`.
2. Add the entry **newest first**, directly under the index, using exactly this template, at most
   25 lines:

```markdown
### ADR-NNN · YYYY-MM-DD · Title
Status: accepted | proposed | superseded by ADR-NNN

**Context:** the problem and the constraint that forced a choice, with the evidence (a measurement,
a doc, an error), not an opinion.
**Decision:** what was chosen, specifically enough to check in code.
**Rejected:** each alternative, and the one reason it lost.
**Consequences:** what this makes easier, what it costs, what now has to stay true.
**Verify / revisit if:** the test or metric that shows it working, and the observation that should
reopen it.
```

3. Add its line to the index: `ADR-NNN · date · title · status`.
4. If the decision changes a spec, update that spec in the same commit and link the ADR from it.

Never record a guess as settled. An untested choice is `proposed` until its verification ran.
