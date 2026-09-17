# Approved UI component sources

Every third-party UI file is source code we own after install. Read it before committing it, adapt
it with the checklist at the bottom, and add it to `CREDITS.md`. Rules on third-party work:
`docs/HACKATHON.md` ("anything you didn't write needs a credit and a licence that permits the use").

## 1. shadcn/ui: the base (MIT)
Init once in M1 (Tailwind v4, CSS variables). Then map shadcn's variables to the tokens in
`docs/DESIGN.md` §3, so no default shadcn look ships.

Components to add, as needed:
- `button` `badge` `card` `separator` `skeleton`
- `dialog` `popover` `tooltip` `tabs`
- `scroll-area` `resizable` (three-pane workspace)
- `sonner` (toasts)
- `input` `textarea` `label`

```bash
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add button badge card separator skeleton dialog popover tooltip tabs scroll-area resizable sonner input textarea label
```

shadcn ships `lucide-react` icons. Replace every visible icon with Phosphor (DESIGN.md §7) and remove
`lucide-react` once nothing imports it: one icon family per product.

## 2. Vengeance UI (MIT), pinned
Repository `github.com/Ashutoshx7/VengeanceUI`, commit `813d9c192b1f82cb36db3d5af93c2ac7d3285ae4`
(2026-08-31). Always install from the pinned raw URL, never from `main` or the website:

```bash
pnpm dlx shadcn@latest add https://raw.githubusercontent.com/Ashutoshx7/VengeanceUI/813d9c192b1f82cb36db3d5af93c2ac7d3285ae4/public/r/<name>.json
```

Reviewed 2026-09-16 (dependencies read from the registry files):

| Component | Use in CROWN-X | Dependencies | Notes |
|---|---|---|---|
| `search-modal` | ⌘K "Ask CROWN" palette: question, recent questions, jump to a conflict | `@phosphor-icons/react` | Already Phosphor. 16 KB, so read it all; strip features we don't show. |
| `border-beam` | Only on the conflict card while "Comparing sources" runs; removed when done | none | Upstream loops forever. Mount it for the duration of real work only. Colour from `--conflict`. |
| `animated-number` | Counters on the workspace header: documents indexed, conflicts found | `framer-motion` | Animate on change only, never on page load. |
| `morphing-disclosure` | "Why was this flagged?" on the conflict card | `framer-motion`, `lucide-react` | Swap the icon to Phosphor. |
| `stagger-text` | Landing headline only | `framer-motion` | Words must be visible without JS and under reduced motion. |
| `highlight-grid` | Landing hero background, very low contrast | none | Check it costs nothing on the app routes; landing only. |

Rejected, with the reason:
- `kinetic-text-loader`: imports a Google Font at runtime (breaks self-hosted fonts and CSP) and
  loops.
- `reveal-loader`: adds GSAP, a second animation library alongside Motion.
- `command`: `lucide-react` + `cmdk`, and duplicates `search-modal`.
- `glow-border-card`, `animated-rays`, `aurora-hero`, `liquid-*`: glow, aurora and neon are the
  generic-AI look this product avoids.
- `expandable-bento-grid`: a bento feature grid inside a work tool.
- `spotlight-navbar`: watches a `dark` class; the app is dark-only.
- `perspective-grid`: renders about 1,600 DOM tiles for a backdrop.

Adding a component not in the table: read its registry JSON at the pinned commit, check dependencies,
network calls, font imports and infinite animations, then record it here and in an ADR.

Note: the Vengeance docs site shows crypto-token promotion. Don't link it from the README, the
writeup or the video; credit the GitHub repository.

## 3. Skiper UI: conditional
`skiper-ui.com` has no public source repository, so a component can't be audited before install, and
the free tier requires attribution. Use one only if it is clearly better than every option above for
a specific need, after reading the downloaded file in full, with attribution in `CREDITS.md` and the
app footer. None is selected today.

## 4. Animmaster Lib: not allowed
A paid bundle distributed through Google Drive and Telegram, with no public licence text or source to
verify. The event rules require a credit and a licence that permits the use; this can't meet that.
Its visual ideas are fair inspiration; its code is not used.

## 5. Design skills (installed by `scripts/install_ui_skills.py`, pinned)
- `design-taste-frontend` from `github.com/Leonxlnx/taste-skill` at
  `ccbc15639c97057cbfcf32ecebc38ef716e4bb37` (MIT). Anti-slop rules and brief inference. Upstream
  scope is landing pages, portfolios and redesigns, not dashboards; so for app surfaces DESIGN.md
  governs and this skill contributes its bans.
- `ui-ux-pro-max` from `github.com/nextlevelbuilder/ui-ux-pro-max-skill` at
  `8bd29e775453ebcae52b6e6514fbf134df0c5770` (MIT). Local search over UX guidelines, charts, stacks and
  palettes, with no network calls in its scripts (checked 2026-09-16). The installer rewrites its
  script path from `${CLAUDE_PLUGIN_ROOT}` to `${CLAUDE_SKILL_DIR}` so it runs as a project skill.

## Adaptation checklist (every installed component)
- [ ] Header comment: source repo, commit SHA, licence, date, what we changed.
- [ ] `framer-motion` imports become `motion/react`. There is one animation library.
- [ ] Icons become Phosphor at the product's weight.
- [ ] Colours, radii, shadows and durations come from DESIGN.md tokens; no raw hex values.
- [ ] Nothing hidden until an animation or observer runs: content is visible if JS or motion is off.
- [ ] `prefers-reduced-motion` gives the final state immediately.
- [ ] No infinite animation unless bound to a real in-progress state.
- [ ] Keyboard reachable, visible focus, labelled for screen readers.
- [ ] Unused props, variants and demo content deleted.
- [ ] Listed in `CREDITS.md`.
