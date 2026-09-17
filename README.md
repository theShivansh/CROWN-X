# CROWN-X Kit v4: Claude Code starter for First Commit 2026

This is the pre-event kit for **CROWN-X**, an evidence-first workspace that answers questions across
evolving project documents, shows where they contradict each other, and cites every claim. It holds
the product specs, the four-day plan, and a Claude Code setup for Opus 5 (subagents, skills, hooks,
MCP, tests).

The event rules allow planning before the start, but not project code. This kit is planning and
tooling only. The application gets built in a fresh repository from Sept 17.

> Replace this README with the product README during M1. Keep the "Working with Claude Code" section.

## What's inside

```text
CLAUDE.md                     project memory, under 120 lines: rules, stack, commands, how to work
CREDITS.md                    AI tools and third-party credits (required by the rules)
.mcp.json                     Playwright (browser verification), AWS documentation
.claude/
  settings.json               permissions (deny secrets, ask before push/deploy) and hooks
  hooks/                      session_start · guard_bash · guard_secrets · format_changed · stop_gate
  agents/                     reviewer · security · evals · ui-verifier
  skills/
    resume/  milestone/  verify-stage/  record-decision/  aws-ship/  release/   (you invoke)
    rag-evidence/  workflow-learning/  crown-ui/                                (Claude loads)
    crown-ui/references/      COMPONENTS.md (approved, pinned UI sources) · ANTI_SLOP.md (bans, checklist)
prompts/                      detailed stage prompts, one per milestone, written for Opus 5
  00-OPENING-BOOTSTRAP.md     first hour: harness live, deadline, M0 facts, demo scenario, M1 planned
  01-M1 … 06-M6               walking skeleton → grounded answers → contradictions → polish → workflows → submit
  07-UI-SCREEN-PASS.md        insert: one screen, every state, verified in the browser
  08-TRIAGE-BEHIND-SCHEDULE.md  insert: cut scope on purpose, Build It fallback
docs/
  PROGRESS.md                 the single state file: next step, milestones, blockers, risks, log
  DECISIONS.md                ADR index + ADR-001..008
  MILESTONES.md               M0-M6: scope, done-means with verification level, kill criteria, prompt
  HACKATHON.md                rules (verified 2026-09-16), plan, video script, submission checklist
  PRD.md  SRS.md  ARCHITECTURE.md  UI_UX.md  DESIGN.md  EVALUATION.md  SECURITY.md  BENCHMARKS.md
scripts/
  install_ui_skills.py        installs taste-skill + ui-ux-pro-max at pinned commits
  validate_kit.py             checks the harness wiring, frontmatter, references, secrets
tests/test_hooks.py           the hooks decide things, so they are tested
.github/workflows/ci.yml      harness checks + gitleaks (M1 adds web and api jobs)
```

## Today (before opening): M0
1. Work through `docs/MILESTONES.md` → M0: AWS account and budget alert, Builder Center verification,
   region, Bedrock model access, local tools. Record results in `docs/PROGRESS.md` of **this kit**.
2. Read `docs/HACKATHON.md`: the four judging criteria and the plan.
3. Don't create the project repository and don't write application code yet.

## At opening (Sept 17)
1. Create a new public GitHub repository and clone it.
2. Copy the **contents** of this kit folder into the repository root, including hidden files
   (`.claude/`, `.mcp.json`, `.gitignore`, `.github/`), so `CLAUDE.md` sits at the root.

   On Windows PowerShell:
   ```powershell
   Copy-Item -Path "C:\path\to\CROWN-X_Kit_v4\*" -Destination . -Recurse -Force
   Get-ChildItem -Force   # confirm .claude, .mcp.json, .github are there
   ```
3. Install the design skills and check the harness:
   ```bash
   python scripts/install_ui_skills.py
   python scripts/validate_kit.py
   python -m pytest tests -q
   ```
4. Commit it all as the first commit, by path, before any application code.
5. Start Claude Code **interactively** at the repository root and accept the workspace trust dialog.
   Until you do, Claude Code ignores the project's permission rules; `claude -p` in an untrusted
   folder says so and skips them. Approve the project MCP servers when asked (Playwright, AWS docs).
6. Check that the setup is live before building:
   - ask "what does the session start hook say?", which should quote the next-session line;
   - ask Claude to run `git add -A`, which should be denied by `guard_bash`;
   - run `/resume`.

   Then paste `prompts/00-OPENING-BOOTSTRAP.md`. It confirms the deadline and M0 facts, writes the
   demo scenario and plans M1. After that, `/milestone M1`.

## The daily loop
```text
/resume                 where things stand: ledger + git, reconciled
/milestone M3           loads prompts/03-…, plans (plan mode) → build → verify → persist → commit
/verify-stage M3        gates with PASS / FAIL / NOT TESTED evidence
/record-decision …      whenever a material choice is made
/aws-ship deploy        when a milestone needs to be live (asks before deploying)
/release                Sunday: freeze, writeup, video check, submit early
```

## Working with Claude Code

| Feature | How this kit uses it | Why |
|---|---|---|
| `CLAUDE.md` | Rules that each name what enforces them; commands; how to work | Loaded every session, so it's short |
| Skills | Workflows you invoke (`disable-model-invocation`), domain rules Claude loads by description | Detail loads only when used; commands are merged into skills |
| Subagents | Four read-mostly specialists with tool limits and output formats | Isolate context-heavy review and verification; building stays in the main session |
| Hooks | SessionStart context, PreToolUse guards (JSON decisions), PostToolUse format, Stop gate (exit 2, loop-safe) | Deterministic enforcement that doesn't rely on memory |
| Permissions | Deny `.env`, keys, force-push; ask before push, deploy, AWS deletes | Safety without a prompt for every routine command |
| MCP | Playwright for real-browser checks; AWS docs for Bedrock, SAM and OpenSearch questions | "Verified live" means a browser, not a status code |
| Bundled skills | `/run-skill-generator` in M1, `/code-review` before closing a milestone, `/rewind` | Built in; no need to re-create them |
| Plan mode | `/milestone` plans before building | Scope is agreed before code |

**Opus 5 notes.**
- Instructions are plain and give reasons, instead of shouting in capitals.
- Delegation happens only for independent, context-heavy work.
- Independent reads and checks run in parallel.
- Progress lives in files and git, not in the conversation.
- Skills that deserve more thought set `effort: high`.

## UI direction (anti-slop)
- **Locked design:** `docs/DESIGN.md`. A dark, precise "instrument" language; neutral surfaces stepped
  by tone; one blue accent; evidence states that always pair colour with an icon and a label; Geist and
  Geist Mono; Phosphor icons; one signature motion sequence. Contrast was computed for every token and
  passes WCAG AA.
- **UI UX Pro Max** was run for this product. Its accessibility and density guidance is used; its
  palette and page pattern were overridden, with reasons in ADR-007.
- **taste-skill** contributes the bans and brief-reading discipline (`ANTI_SLOP.md`).
- **Vengeance UI:** six components approved at a pinned commit, each with a specific job, and seven
  rejected with reasons (`COMPONENTS.md`).
- **Skiper UI:** conditional; there's no public source to audit.
- **Animmaster Lib:** not used; it's a paid bundle with no verifiable licence, and the rules require
  one.

## Requirements
- `python` on PATH (3.11 or newer) for the hooks and scripts. On macOS or Linux, if only `python3`
  exists, change `"command": "python"` in `.claude/settings.json`.
- Git, Node 22 with pnpm, uv (for the AWS docs MCP server), AWS CLI, SAM CLI, Docker.

## What changed from kits v1-v3
| Problem in v1-v3 | Fixed in v4 |
|---|---|
| `.claude/` and `CLAUDE.md` nested in `09_CLAUDE_CODE/`, so Claude Code never loaded them | Kit laid out as a repository root |
| Two hooks printed to stderr with exit 0; Claude never saw them | Hooks return decisions; the Stop gate blocks on real lint and typecheck failures and can't loop |
| Secret guard missed Anthropic, Groq and GitHub keys and `.env` writes | Broader patterns, env files blocked, all covered by tests |
| Relative hook paths broke when the working directory changed | `${CLAUDE_PROJECT_DIR}` in `args` |
| Eight agents with no tool limits, five on Opus | Four agents with tool limits and output formats |
| Eight state files to update per milestone | `docs/PROGRESS.md` plus `docs/DECISIONS.md` |
| No browser verification | Playwright MCP in every stage's done-means; a `ui-verifier` agent for an independent pass on request |
| Rules from the older rulebook (five criteria including "Learning") | Rules re-verified 2026-09-16: four criteria, Best UI open to both tracks, AI tools must be named |
| Workflow Learning Lite marked P0 while the plan treated it as removable | Gated behind M4 (ADR-005) |
| PRD, SRS and UI spec split across kits with different detail | Merged; SRS has the data model, API and error table; UI spec has every state |
| No design system, no library policy | `DESIGN.md`, `COMPONENTS.md`, `ANTI_SLOP.md`, pinned design skills |
