# Anti-slop rules and pre-delivery checklist

Distilled for CROWN-X from `design-taste-frontend` (taste-skill, MIT) and `ui-ux-pro-max` (MIT), then
narrowed to this product. Where this file and DESIGN.md differ, DESIGN.md wins.

## 1. The look to avoid
These are the defaults an AI reaches for, and judges have seen them all:
- purple-to-blue gradients, glowing buttons, aurora or mesh backgrounds, neon on dark
- a centred hero over a dark blur with three equal feature cards under it
- glassmorphism on every surface
- sparkle icons marking anything "AI"
- Inter on `slate-900`; or a random serif word dropped into a sans headline
- emoji as icons or bullet decoration
- everything animating on load; infinite pulses with nothing running
- fake metrics: "98% accuracy", "10x faster", an unexplained confidence ring
- Lorem ipsum, "Acme Corp", "John Doe", generic avatars

## 2. What CROWN-X does instead
- One restrained accent (`--accent`). Colour otherwise carries meaning only: grounded, conflict,
  insufficient, error.
- Evidence is the visual hero: quoted spans in Geist Mono, source name, version and date beside every
  value.
- Hierarchy from type size, weight and space, not from boxes inside boxes.
- Surfaces separated by 1px borders and a small step in background tone; no drop shadows on dark.
- Motion explains cause and effect: retrieval produces evidence, evidence produces the conflict, the
  answer locks to its citations.

## 3. Layout
- App: three panes (DESIGN.md §5). Panes resize; nothing essential hides below the fold at 1440x900.
- Use CSS Grid for page structure; no percentage-width flex arithmetic.
- `min-h-dvh`, never `h-screen`, for full-height layouts.
- Tabular figures (`font-variant-numeric: tabular-nums`) for every value, date and count.

## 4. Copy
- Say what happened and what to do next: "No passage mentions a deadline. Upload the latest brief,
  or ask about another field."
- Banned: elevate, seamless, unleash, supercharge, next-gen, game-changer, revolutionize, delve,
  "AI-powered" as a label.
- No em dashes in UI strings. Use a colon, a comma or two sentences.
- Stage labels name the work: "Parsing brief-v2.pdf", "Comparing 2 sources". Not "Step 2 of 4".
- Uncertainty in words: "Sources disagree", "Not enough evidence". Never a bare percentage.

## 5. Accessibility floor
- Text contrast 4.5:1 or more, large text and icons 3:1. DESIGN.md tokens already meet it; don't
  lower opacity on text to "soften" it.
- Every state has an icon **and** a label; colour is never the only signal.
- Keyboard: every action reachable, focus ring always visible (`--ring`), ⌘K / Ctrl+K opens Ask,
  Esc closes overlays, arrow keys move within evidence lists.
- Targets at least 24x24px (44x44 for primary actions).
- Reduced motion shows the final state immediately; no content waits for an animation.

## 6. Pre-delivery checklist
Run in the browser through Playwright MCP before calling any screen done.
- [ ] Matches DESIGN.md tokens: no raw hex, font, radius or duration in components.
- [ ] One icon family (Phosphor), one weight; no emoji.
- [ ] Loading, empty, partial, insufficient-evidence, conflict and error states designed and reachable.
- [ ] Loading names real work, and resolves per item (each document card independently).
- [ ] No banned pattern from §1 or banned word from §4.
- [ ] Evidence visible for every factual claim on screen, openable to the passage.
- [ ] 1440x900 and 1024x768: no horizontal scroll, no clipped text, panes usable.
- [ ] Keyboard-only run of the demo path works; focus always visible.
- [ ] Reduced motion: everything visible and still.
- [ ] Console clean; no layout shift when evidence arrives (space reserved).
- [ ] Demo data realistic and consistent with the seeded documents.
