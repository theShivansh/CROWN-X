# CROWN-X

Evidence-first project context workspace. Upload evolving project documents, ask a question, and get
an answer that cites its sources, shows where the sources disagree, and shows how a value changed
over time. Built for AWS First Commit 2026 (Sept 17-20).

## Read first
- `docs/PROGRESS.md`: what is done and what is next. The repo overrules it; memory overrules neither.
- `docs/MILESTONES.md`: the current milestone's scope, done-means and kill criteria.
- `prompts/`: the detailed stage prompt for that milestone (`prompts/README.md` gives the order).
- `docs/DECISIONS.md`: read the index, then only the entries the task touches.
- Specs, when the milestone names them: `docs/PRD.md`, `docs/SRS.md`, `docs/ARCHITECTURE.md`,
  `docs/UI_UX.md`, `docs/DESIGN.md`, `docs/EVALUATION.md`, `docs/SECURITY.md`, `docs/HACKATHON.md`.

## Stack
- Web: Next.js App Router, TypeScript strict, Tailwind CSS v4, shadcn/ui components we own, Motion
  (`motion/react`), Geist + Geist Mono, Phosphor icons. Hosted on AWS Amplify.
- API: Python 3.12 on AWS Lambda behind API Gateway (HTTP API), Pydantic v2 contracts, AWS SAM.
- Data: S3 (raw documents), OpenSearch (retrieval), DynamoDB (metadata, conflicts, audit, events),
  Amazon Bedrock (generation), CloudWatch (logs and metrics).

## Commands
Fill these in during M1 and keep them exact, so they are run rather than guessed.
- install: api `cd services/api && uv sync` | web `cd apps/web && pnpm install --frozen-lockfile`
- dev web: `cd apps/web && pnpm dev` (needs `NEXT_PUBLIC_API_URL` in the environment) | dev api: `TBD`
- test: api `cd services/api && uv run pytest -q` | harness `python -m pytest tests -q` | web `cd apps/web && pnpm test`
- lint: api `cd services/api && uv run ruff check src tests` | infra `uvx cfn-lint infra/template.yaml` | web `cd apps/web && pnpm lint`
- typecheck: web `cd apps/web && pnpm typecheck` | build: web `cd apps/web && pnpm build` (static export to `apps/web/out`) | Lambda deps: `cd services/api && uv export --no-dev --no-hashes --no-emit-project --format requirements-txt -o src/requirements.txt`
- eval: offline `cd services/api && uv run python ../../evals/run.py --offline [--embedding bge-small-en-v1.5-int8]` | retrieval benchmark `... --compare [--dataset paraphrase|retrieval-v2]`, live without Groq `... --api <ApiUrl> --retrieval-only --dataset retrieval-v2` | workflow `cd services/api && uv run python ../../evals/workflow_eval.py` | live `... --api <ApiUrl> --pace 2.5`
- local models: `python scripts/fetch_models.py` (into `services/api/.models/`, gitignored) | publish `... --publish <DocumentsBucket>`
- deploy (always ask first): `sam deploy` and the Amplify publish step recorded in `/aws-ship`

## Rules that don't bend
Each rule names what enforces it. "prose" means nothing does yet; add a test when it matters.
1. Every factual answer carries evidence IDs that resolve to stored chunks, or it says the evidence
   is insufficient. (test: citation contract)
2. The conflict predicate is deterministic code. A model may extract or normalize claims; it never
   decides that two values conflict. (test: contradiction engine)
3. Retrieved document text is untrusted data. It cannot change instructions, tools or permissions.
   (test: injection cases in the eval set)
4. Workspace scope is enforced before any retrieval result reaches a model. (test: cross-workspace)
5. No secrets in the repo; credentials come from the environment or AWS.
   (hooks: guard_secrets, permissions deny `.env`; CI: gitleaks)
6. Never report a test as passing, a resource as existing, or a deploy as working without having
   observed it in this session. (prose)
7. Commit by explicit path. No force-push and no history rewrite: judges check that repo history
   matches the event window. (hook: guard_bash)
8. Scope is frozen per milestone. A new idea goes to the Parking lot in `docs/PROGRESS.md` unless it
   strengthens the three-minute demo. (prose)
9. UI follows `docs/DESIGN.md`. A value outside its tokens needs a DECISIONS entry. (skill: crown-ui)
10. No confidence number reaches the UI unless its meaning is defined and measured.
    (docs/EVALUATION.md)

## Definition of done
A milestone is done when every done-means item in `docs/MILESTONES.md` passed at the level it names:
- `unit`: tests with test doubles
- `integration`: real AWS or local services
- `live`: the deployed URL, walked through in a browser

Then PROGRESS is updated, decisions are recorded, and a commit is made. `/verify-stage` runs this.

## How to work
- Start every session with `/resume`. `/milestone <id>` loads that stage's prompt from `prompts/` and
  plans it in plan mode before building.
- **Scope.** Deliver what the milestone asks for, at the scope it intends. Make routine judgment calls
  yourself; check in only when different readings would lead to materially different work. If the
  plan looks mistaken, say so in a sentence and continue as asked. Finish the whole milestone before
  reporting it done; if something can't be finished, do the rest and state plainly what's missing and
  why.
- **Verification** is part of the work, done in this session: run the checks the done-means name and
  read their output. Don't rerun a check you already saw pass unless the code changed since.
- **Subagents** multiply time and cost: each one re-establishes context, and you then re-read its
  report. Use one only for a large, genuinely independent track, such as a wide investigation across
  many files, and never for review or verification. The project agents (`reviewer`, `security`,
  `evals`, `ui-verifier`) are for when the user asks for an independent pass.
- Run independent reads and commands in parallel.
- **When a check fails:** reproduce it, fix the root cause, then rerun that check and the affected
  suite. Never weaken a test or add a fallback that hides a failure.
- **Writing for the user:** lead with the outcome, in complete sentences, for a teammate catching up.
  Mention a correction only when it changes their code or decisions. Documents you write are as long
  as their content needs.
- **Bundled skills:**
  - `/run-skill-generator` once in M1
  - `/code-review` when the user wants a review pass
  - `/rewind` instead of hand-reverting a wrong direction

## Project skills
You invoke: `/resume`, `/milestone`, `/verify-stage`, `/record-decision`, `/aws-ship`, `/release`.

Claude loads when relevant:
- `rag-evidence`, `workflow-learning`, `crown-ui`
- the pinned third-party design skills `design-taste-frontend` and `ui-ux-pro-max`, installed by
  `python scripts/install_ui_skills.py`

For UI conflicts, precedence is: this file, then `docs/DESIGN.md`, then `crown-ui`, then
`ui-ux-pro-max` results, then `design-taste-frontend` defaults.

## Session protocol
1. `/resume`.
2. Work one milestone, or the next slice of one.
3. Before stopping:
   - update the "Next session starts here" line in `docs/PROGRESS.md`
   - update the milestone row and its verification level
   - record material decisions with `/record-decision`
   - commit by explicit path
