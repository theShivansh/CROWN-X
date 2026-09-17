# 07 · UI screen pass (insert, repeatable)

**Screen for this pass:** name it when you paste this prompt, for example "conflict inspector",
"ingestion cards", "timeline", "Ask palette", or "landing page". One screen per run.

Build or polish that one screen so it looks deliberate, works in every state a user can reach, and
holds up in a three-minute video watched by judges scoring Best UI. The failure mode to design away
from is the generic AI dashboard: glowing gradients, sparkle icons, equal feature cards, everything
animating. CROWN-X's look is calm precision, where the evidence is the visual hero.

## Read first
- `.claude/skills/crown-ui/SKILL.md`, which sets the precedence order
- `docs/DESIGN.md` (all)
- the screen's section of `docs/UI_UX.md`
- `.claude/skills/crown-ui/references/COMPONENTS.md` and `ANTI_SLOP.md`
- the current code for the screen and the components it uses

## Work through it

**Design read.** Open with one line in the form `Reading this as: <screen> for <audience>, <language>,
dials V/M/D` (app surfaces 3/3/6, landing 6/5/3). If the screen's job in the golden path isn't clear
from UI_UX, say what you take it to be.

**State inventory.** Before building, list every state the screen can be in, from the API contracts
and UI_UX:
- loading, with the real stage names;
- empty;
- the normal populated state;
- partial;
- insufficient evidence;
- conflict;
- error, with `request_id` and a recovery action;
- very long content (a 200-character filename, a 5-paragraph evidence span);
- many items (20 documents, 12 evidence cards);
- narrow width (1024 and 768).

Each gets a designed rendering, not a fallback.

**Answer open UX questions from the local database, briefly.** For a question the docs don't settle,
query the installed skill with one intent and a few terms, for example:
- `python .claude/skills/ui-ux-pro-max/scripts/search.py "side by side comparison readability" --domain ux`
- `python .claude/skills/ui-ux-pro-max/scripts/search.py "keyboard list navigation" --domain ux`
- `python .claude/skills/ui-ux-pro-max/scripts/search.py "timeline accessibility" --domain chart`

Use what fits the product; DESIGN.md wins any disagreement. Don't regenerate a design system.

**Build from owned parts.**
- shadcn/ui primitives re-themed to the tokens;
- approved components from COMPONENTS.md, adapted with its checklist and credited in `CREDITS.md`;
- everything else from primitives.

Tokens only: no raw hex, pixel radius or duration in components. Phosphor icons only. Semantic states
always pair colour with an icon and a label (DESIGN §7).

**Motion.**
- Functional feedback at the fast durations.
- Spatial entrances only where they explain cause and effect.
- On workspace screens, only the signature sequence (DESIGN §6) animates at hero scale.
- Nothing loops unless a real process is running.
- `prefers-reduced-motion` shows the final state immediately.

**Copy.**
- Say what happened and what to do next, in plain words (ANTI_SLOP §4).
- Stage labels name the work.
- No em dashes in UI strings; no marketing adjectives.
- Demo content matches `demo/SCENARIO.md`.

**Accessibility.**
- Landmarks and headings.
- Keyboard: every action reachable, logical focus order, arrow keys within lists and tracks, Esc
  closes overlays, and focus returns to the trigger.
- Visible focus ring.
- Live-region announcements for stage changes and "Answer ready".
- Reserve space for arriving content so nothing shifts.

## See it
Run the app, locally with the mocked or dev API or on the deployed URL, and check the screen through
Playwright MCP:
- every state from the inventory, reached for real where possible, or through test fixtures;
- at 1440x900, 1024x768 and 768 wide;
- keyboard only;
- with reduced motion emulated;
- the console clean;
- the ANTI_SLOP §6 checklist.

Take screenshots of the normal and conflict states at 1440 and save them under
`docs/screenshots/<screen>/`; the README and video prep reuse them. Fix what you find, and look again
at what you fixed.

## Done means for the pass
- [ ] Every state in the inventory designed, reachable and screenshotted where it matters
- [ ] ANTI_SLOP §6 checklist passes at 1440, 1024 and 768, keyboard only and with reduced motion
- [ ] Component tests (vitest + Testing Library) for state rendering and keyboard behaviour; an
  `@critical` e2e step if the screen is on the golden path
- [ ] Third-party components credited; no new icon family, animation library or font

## Finish
Commit by path. Add one line to the PROGRESS verification log naming the screen and states covered.
Report:
- what changed visually, in two or three sentences;
- the screenshot paths;
- any state that still falls short, and why.
