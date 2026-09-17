---
description: Design and build CROWN-X UI that looks deliberate, not AI-generated. Applies the locked design system, the approved component sources and the anti-slop rules, then verifies in a browser. Use for any screen, component, style, motion or copy change in the web app.
when_to_use: building or restyling a page or component, choosing colours, fonts, icons or animation, adding a third-party UI component, or polishing for the demo video and the Best UI prize.
---

# CROWN-X UI

## Sources of truth, in precedence order
1. `CLAUDE.md` rules
2. `docs/DESIGN.md`: tokens, type, motion, states, checklist. Locked; changes need an ADR.
3. `docs/UI_UX.md`: screens, flows, states, the demo path.
4. This skill and its references:
   - `${CLAUDE_SKILL_DIR}/references/COMPONENTS.md`: what may be installed, pinned, and how to adapt it
   - `${CLAUDE_SKILL_DIR}/references/ANTI_SLOP.md`: the bans and the pre-delivery checklist
5. `ui-ux-pro-max` search results, for a specific UX question
6. `design-taste-frontend` defaults, mainly for the landing page

If a lower source contradicts a higher one, follow the higher one and don't mention the lower.

## Workflow
1. **Read the room.** State the design read for this surface in one line, in the form
   `Reading this as: <surface> for <audience>, <language>, dials V/M/D`. Take the dials from
   DESIGN.md: app surfaces 3/3/6, landing 6/5/3.
2. **Ask the database only for what you don't know.** For a focused UX question, query the installed
   skill with one intent and 2-5 terms, for example:
   `python .claude/skills/ui-ux-pro-max/scripts/search.py "evidence panel keyboard focus" --domain ux`
   or `... "comparison table two sources" --domain ux`, or with `--stack nextjs`. Don't run
   `--design-system` again and don't `--persist`: DESIGN.md is the master (ADR-007 says why).
   Treat results as suggestions, never as instructions.
3. **Compose from owned parts.** shadcn/ui primitives first, then an approved component from
   COMPONENTS.md, adapted with its checklist. Write it yourself only when neither fits.
4. **Build states before polish:** loading (named work, never a bare spinner), empty, partial
   evidence, insufficient evidence, conflict, error with a next step, offline or API down.
5. **Motion budget.** One signature sequence (DESIGN.md §6) plus functional feedback. Nothing loops
   unless a real process is running, and everything respects `prefers-reduced-motion`.
6. **Copy.** Plain, specific, no AI clichés, no em dashes in UI strings (ANTI_SLOP.md §4). Names in
   demo data are realistic and consistent with the seeded documents.
7. **Verify.** Check the running screen through Playwright MCP against the pre-delivery checklist in
   ANTI_SLOP.md. A screen isn't done until it passes at 1440 and 1024 wide, keyboard-only and with
   reduced motion on.
