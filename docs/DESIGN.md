# CROWN-X design system

Locked for the hackathon. A change needs an ADR (`/record-decision`). Screens and flows are in
`docs/UI_UX.md`; how to apply this is in the `crown-ui` skill.

## 1. Design read
> Reading this as: an evidence-first AI workspace for technical project teams, and for judges scoring
> Best UI from a three-minute video, with a calm, precise, dark "instrument" language (Linear-grade
> restraint, evidence as the hero), leaning toward Next.js + Tailwind v4 + shadcn/ui we own + Geist
> + Motion.

**Dials** (variance / motion / density, 1-10):
- App surfaces: **3 / 3 / 6**. Predictable structure, functional motion, information-dense but
  breathable.
- Landing page: **6 / 5 / 3**.

## 2. How this was decided
- `ui-ux-pro-max` design-system run, 2026-09-16, query "AI evidence document workspace developer
  tool", dials 4/3/7. **Kept:** its style (dark, high contrast, visible focus, reduced motion), its
  accessibility checklist, a dense spacing scale, and a monospace face for data. **Overrode:** its
  page pattern ("FAQ/Documentation landing": a wrong match for a workspace), its slate-navy + green
  palette (the generic dev-tool look, and green is our *grounded* state, so it can't also be the
  brand), and its JetBrains Mono + IBM Plex pair (one family, Geist, reads cleaner at small sizes).
- `design-taste-frontend` rules applied: one accent, neutral base rather than slate, no AI purple, no
  default Inter, Phosphor over Lucide, `motion/react`, `min-h-dvh`, the copy bans.
- Contrast: every text token was computed against every surface (table below). All pass WCAG AA.

## 3. Tokens (dark only for the hackathon; light theme is post-event)
Paste into the web app's global CSS in M1:

```css
@import "tailwindcss";

@theme {
  /* Surfaces: neutral near-black, stepped by tone rather than shadow */
  --color-bg: #0a0a0b;
  --color-surface: #111113;
  --color-surface-2: #18181b;
  --color-surface-3: #202024;
  --color-border: rgb(255 255 255 / 0.08);
  --color-border-strong: rgb(255 255 255 / 0.14);

  /* Text */
  --color-text: #ededef;
  --color-text-muted: #a1a1aa;
  --color-text-subtle: #8b8b93;

  /* Brand accent: interactive and "newer source" only */
  --color-accent: #6e9bff;
  --color-accent-fg: #0a0a0b;
  --color-accent-soft: rgb(110 155 255 / 0.12);
  --color-ring: #6e9bff;

  /* Evidence states: always paired with an icon and a label */
  --color-grounded: #3dd68c;
  --color-grounded-soft: rgb(61 214 140 / 0.12);
  --color-conflict: #f5a524;
  --color-conflict-soft: rgb(245 165 36 / 0.12);
  --color-insufficient: #a1a1aa;
  --color-error: #f87171;
  --color-error-soft: rgb(248 113 113 / 0.12);

  /* Type */
  --font-sans: var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif;
  --font-mono: var(--font-geist-mono), ui-monospace, "SFMono-Regular", monospace;

  /* Radius */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;

  /* Motion */
  --duration-fast: 120ms;
  --duration-base: 180ms;
  --duration-spatial: 280ms;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
}
```

| Token | On bg | On surface | On surface-2 | Use |
|---|---:|---:|---:|---|
| text `#EDEDEF` | 16.9 | 16.1 | 15.2 | body, headings |
| text-muted `#A1A1AA` | 7.7 | 7.4 | 6.9 | secondary text, labels |
| text-subtle `#8B8B93` | 5.9 | 5.6 | 5.2 | metadata only |
| accent `#6E9BFF` | 7.4 | 7.0 | 6.6 | links, focus, newer source |
| grounded `#3DD68C` | 10.6 | 10.1 | 9.5 | grounded answer |
| conflict `#F5A524` | 9.7 | 9.2 | 8.7 | conflict |
| error `#F87171` | 7.2 | 6.8 | 6.4 | failure |

Buttons with an accent background use `--accent-fg` (contrast 7.4). White on the accent is only 2.7,
so never use it.

## 4. Typography
- Geist Sans for UI; Geist Mono for evidence quotes, IDs, values, dates, counts. Load through
  `next/font` (self-hosted); never a runtime Google Fonts link.
- Scale (px / line-height): 12/16 meta · 13/18 dense lists · 14/20 body · 16/24 lead ·
  20/28 section · 24/32 page title · 32/38 landing H2 · 44/48 landing H1 (weight 600, tracking
  -0.02em).
- `tabular-nums` on every number and date. Max body measure 72ch.
- Emphasis: weight or italic of the same family. No mixed-family words.

## 5. Layout and density
- Spacing base 4px. Scale: 4, 8, 12, 16, 20, 24, 32, 48. App gutters 16, panel padding 16-20.
- App shell (at 1440 wide): left rail 264px (workspace, documents) · centre flexible (ask and answer)
  · right evidence panel 400px. Panels resize; at 1024 the evidence panel becomes a sheet.
- Borders separate regions: 1px `--border`. Radius: controls `sm`, cards `md`, sheets and dialogs
  `lg`. No drop shadows on dark surfaces; overlays use `surface-3` plus a border.

## 6. Motion
- Functional (hover, press, toggle): `--duration-fast` / `--duration-base`, `--ease-out`.
- Spatial (panels, sheets, cards entering): `--duration-spatial`.
- **The one signature sequence** (the demo moment): the question is submitted → evidence cards enter
  one by one as retrieval returns (stagger 60ms) → the conflict card appears between the two sources
  with a border beam **while comparison runs** → the answer text settles and its citation chips link
  to the cards. Nothing else on the page moves.
- Never: parallax, scroll-jacking, infinite ambient motion, animating layout properties.
- `prefers-reduced-motion`: final state immediately, no beam, no stagger.

## 7. Iconography
Phosphor (`@phosphor-icons/react`), weight `regular` at 16/20px, `bold` only for the state icon inside
a badge. One family everywhere, no emoji.

| State | Icon | Colour | Label |
|---|---|---|---|
| Grounded | `SealCheck` | grounded | "Supported by 3 sources" |
| Conflict | `GitDiff` | conflict | "Sources disagree" |
| Insufficient | `Question` | insufficient | "Not enough evidence" |
| Error | `WarningOctagon` | error | what failed plus the next step |
| Newer source | `ClockClockwise` | accent | "Newer · 22 Sep" |
| Processing | `CircleNotch` (rotating only while working) | text-muted | the work being done |

## 8. Components we own
Base primitives: shadcn/ui re-themed to these tokens. Approved enhancements and their exact use:
`.claude/skills/crown-ui/references/COMPONENTS.md`. Anything else is built from primitives.

## 9. Pre-delivery checklist
The checklist in `.claude/skills/crown-ui/references/ANTI_SLOP.md` §6 is the gate. Check it in a real browser
with Playwright MCP (`prompts/07-UI-SCREEN-PASS.md`).
