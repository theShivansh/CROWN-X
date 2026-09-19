# Credits

The event rules require naming AI coding tools, and a credit plus a permitting licence for anything
not written during the event. Everything in this repository was written between 2026-09-17 13:18 IST
(the first commit) and the submission, except what's listed below.

## AI coding tools
- **Claude Code with Claude Opus 5** (Anthropic): planning, implementation, tests, reviews,
  deployment scripts and verification across every milestone. The working method is in
  `CLAUDE.md` and `.claude/`.
- **GitHub Copilot**: inline completions in the editor.

## Models the product runs (services, not coding tools)
| Model | Where it runs | Used for | Licence |
|---|---|---|---|
| `openai/gpt-oss-120b`, falling back to `openai/gpt-oss-20b` | Groq API | writing answers over the retrieved evidence; naming a detected workflow | open-weight, Apache-2.0 (OpenAI); served by Groq under its terms |
| `bge-small-en-v1.5` (int8 ONNX export by Xenova, commit `ea104dac`) | in the Lambda, onnxruntime | passage and question embeddings | MIT (BAAI) |
| `ms-marco-MiniLM-L-6-v2` (int8 ONNX export by Xenova, commit `a0914435`) | in the Lambda, off by default | optional cross-encoder rerank, measured and left off (ADR-017) | Apache-2.0 |
| `multilingual-e5-small` (int8 ONNX export by Xenova, commit `761b726d`) | benchmark only | the retrieval comparison in `docs/BENCHMARKS.md` | MIT (intfloat) |

The model weights aren't in the repository: `scripts/fetch_models.py` downloads them at pinned
commits and checks their sha256.

## Design and development skills (pinned; see `.claude/skills/THIRD_PARTY_SKILLS.md` after install)
| Skill | Source | Commit | Licence |
|---|---|---|---|
| design-taste-frontend | github.com/Leonxlnx/taste-skill | ccbc15639c97057cbfcf32ecebc38ef716e4bb37 | MIT |
| ui-ux-pro-max | github.com/nextlevelbuilder/ui-ux-pro-max-skill | 8bd29e775453ebcae52b6e6514fbf134df0c5770 | MIT |

## UI components
| Component | Source | Licence | Changes made |
|---|---|---|---|
| shadcn/ui primitives: button, input, badge, skeleton (shadcn CLI 4.21, style radix-nova, 2026-09-17) | github.com/shadcn-ui/ui | MIT | colour variables mapped to `docs/DESIGN.md` tokens; control radius `sm`; Lucide replaced by Phosphor |

These were written here, following the component *roles* listed in
`.claude/skills/crown-ui/references/COMPONENTS.md`. No Vengeance UI code was installed or copied:
- `border-beam` (CSS, runs only while sources are compared);
- the "Why was this flagged?" disclosure (`motion/react`);
- the Ask CROWN palette (a native `<dialog>`);
- `animated-number` (`motion/react`).

The reason was their dependencies (`framer-motion`, `lucide-react`) and looping animations.

## Libraries
Full lists are in the lockfiles: `apps/web/pnpm-lock.yaml` and `services/api/uv.lock`. The main ones,
with licences read from their package metadata on 2026-09-19:
- **Web:** Next.js 16 (MIT), React 19 (MIT), Motion (MIT), Zod (MIT), Radix UI (MIT),
  Tailwind CSS 4 (MIT), Playwright (Apache-2.0, tests only), Vitest (MIT, tests only).
- **API:**
  - AWS Lambda Powertools (MIT), boto3 (Apache-2.0), opensearch-py (Apache-2.0);
  - Pydantic (MIT), pypdf (BSD-3-Clause), onnxruntime (MIT), Hugging Face tokenizers (Apache-2.0),
    NumPy (BSD-3-Clause and others);
  - fpdf2 (LGPL-3.0, used only to build the demo PDF and in tests; not deployed).

## Fonts and icons
- Geist and Geist Mono (Vercel), SIL Open Font License 1.1
- Phosphor Icons, MIT

## Demo data
The demo documents in `demo/documents/` and every evaluation dataset in `evals/` were written for
this project during the event. Names in them (Team Lantern, FestPass, and the people) are fictional.
