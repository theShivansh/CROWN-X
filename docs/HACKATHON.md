# First Commit 2026: rules, plan, video and submission

## 1. Rules (re-checked 2026-09-16 23:40 IST and 2026-09-17 07:39 IST; rulebook "last updated September 16, 2026")
Sources: `wemakedevs.org/aws/first-commit` (overview: prizes, tracks, judging, credits), `/rules` (one
rulebook for the whole six-hackathon tour), `/schedule` (hours and deadline). Re-check the schedule
page and record the exact submission deadline (with time zone) in `docs/PROGRESS.md`.

**Changed since the 2026-09-09 check** (the text below is corrected to match the pages):
- Judging lists **five** criteria, including **Learning**. The kit's "four criteria" was wrong for this
  event.
- AWS credits are **$100 per team**, not per participant; codes go to registered participants before
  the start.
- One submission is considered for Ship It, Build It and Best UI together; there is nothing to pick.
- Each hackathon needs its own **check-in** on its page; entrants must be 18 or older.
- A submission can be edited until the deadline; nothing can be submitted or edited after it.
- The overview no longer says Built on AWS "decides most" of the score. Ship It is "where the grand
  prize is decided", and architecture and cost are judged only in Ship It.
- The clock starts **2026-09-17 08:00 IST** (the schedule countdown targets `2026-09-17T02:30:00Z`).
  The deadline is still unpublished at 07:39 IST: the schedule says the hours are "being finalised".

**Event:** online Thursday to Sunday, Sept 17-20, anywhere in India; optional in-person hack day on
Sept 19, 8 AM-8 PM, at Polaris School of Technology, Bangalore (its own Luma signup; attending adds
nothing to the score). Teams of 1-4. Each member is a university student in India aged 18 or older,
registered for the tour individually, with a verified AWS Builder Center student profile, and checked
in to First Commit on its page.

**The clock is the rule:**
- Project work starts when the hackathon opens (2026-09-17 08:00 IST) and ends at the deadline on the
  schedule page. Learning, planning and practice before that are allowed.
- Prior work doesn't qualify, even rewritten. Bring skills, not a repository.
- Open-source libraries, frameworks, public APIs, boilerplate and starter templates are fine, as long
  as what is judged is what you added during the event.
- AI coding tools are allowed; **name them in the writeup**.
- Anything you didn't write needs a credit and a licence that permits the use.
- The project has to use AWS **and the demo video has to show it**; naming AWS only in the writeup
  isn't enough.
- Plagiarism, prior work passed off as new, or **repo history that doesn't match the event dates**
  disqualifies the whole team.

**Submission:** public repository + demo video of up to three minutes + short writeup (problem, build,
where AWS fits), through First Commit's own form, once per team. Submit early: a submission can be
edited until the deadline, and nothing can be submitted or edited after it. Judges score only what is
submitted: no live demo, no call. A feature the video doesn't show, or that exists only in the writeup,
doesn't count.

**Judging (five criteria, from the overview page):**
1. **Idea and impact:** a real problem, and what changes for the people who have it. A small problem
   solved well beats a big one solved vaguely.
2. **Built on AWS:** Ship It (AWS services) "is where the grand prize is decided"; Build It runs the
   open-source AWS stack locally (Strands, PartyRock, Cedar, SAM CLI + LocalStack, OpenSearch). Using
   AWS services or an AWS open-source project is mandatory to win a prize. Architecture and cost
   decisions are judged only in Ship It.
3. **Learning:** what the four days taught the team (a first deploy, a first agent, a new service).
   "Tell us what you learned, and it counts towards your score."
4. **Execution:** does it work? One working feature beats five that almost do.
5. **The demo video:** three minutes showing what it does, who it's for and where AWS fits.

"We judge what you built, not what you spent." Best UI is judged on design and usability.

**Prizes** (one submission is considered for all three tracks):
- **Ship It** (deployed on AWS with a URL): first prize, ₹2,00,000 + $3,000 in AWS credits.
- **Build It** (open-source AWS stack on your machine): second prize, ₹1,50,000 + $2,000 in credits.
- **Best UI** (either track): third prize, ₹1,00,000 + $1,000 in credits.
- Four runners-up: $1,000 in credits per team. Top five blogs on AWS Builder Center, linked in the
  submission: a keyboard each. Tour swag for the top teams.
- **$100 AWS credits per team**, on top of new-account credits; codes arrive before the start.

**Fast-track interview:** up to ten students from top projects (graduating 2027 or 2028) may get a
fast-track interview for a six-month internship or a full-time role. It's decided separately from
prizes, and eligibility is checked against the registration and a verified Builder Center profile.

## 2. What this means for CROWN-X
- One end-to-end flow that works on the deployed URL beats breadth. Workflow Learning Lite is gated
  (ADR-005).
- Ship It decides the grand prize and is the only track where architecture and cost are judged: the
  architecture, the reason for each service and the cost guardrails must be visible in the video and
  the writeup, not only in the README.
- Learning is scored: add a line to the Learning log in `docs/PROGRESS.md` when something is learned,
  so the writeup can report it honestly.
- Best UI is winnable with the conflict inspector; UI polish is scheduled (M4), not squeezed in.
- Submit a working version early on Sunday, then keep editing until the deadline.
- Commit early and often from the first hour, never before 08:00 IST on Sept 17. Never rewrite
  history.

## 3. Four-day plan with gates
Times are targets; the gate matters more than the hour.

| When | Milestone | Gate (from docs/MILESTONES.md) |
|---|---|---|
| Before opening | M0 preparation | Accounts, Bedrock access, tools, skills installed, no project code |
| Thu, Sept 17 | M1 walking skeleton, deployed | Upload one file and ask one question on the deployed URL: a cited answer |
| Thu night to Fri | M2 grounded answers + eval baseline | Citations validated; insufficient-evidence path; baseline recorded |
| Fri, Sept 18 | M3 contradictions + conflict inspector | Seeded conflict detected live; rough demo recording made |
| Sat, Sept 19 | M4 timeline, UI polish, reliability | Golden path live without rescue; browser checklist clean; logs by request ID |
| Sat night (optional) | M5 Workflow Learning Lite | Only if M4 is green by Saturday evening |
| Sun, Sept 20 | M6 freeze and submit | Submitted early; then only fixes until the deadline |

**Kill criteria.** Cut a feature immediately when it:
- adds another infrastructure dependency;
- needs more than a few hours to become reliable;
- can't be shown clearly in the three-minute video;
- doesn't strengthen the core problem;
- puts the golden path at risk after Saturday evening.

## 4. Demo video script (three minutes or less)
Record at 1440x900, dark UI, zoom the browser for legibility, no dead air.

| Time | Section | On screen |
|---|---|---|
| 0:00-0:20 | Problem | Two real-looking documents: "Submissions close 20 September" / "moves to 22 September". "Document chat answers without telling you the sources disagree." |
| 0:20-0:35 | Who and what | "For project teams juggling versions. CROWN-X indexes your documents, answers with evidence and shows conflicts." Upload the three files; stages visible. |
| 0:35-1:30 | Core demo | Ctrl+K → "What is the current submission deadline?" Evidence arrives, conflict card appears, answer settles. Click a citation to show the highlighted passage. Open the conflict inspector: both sources, dates, selection rule. |
| 1:30-1:55 | Timeline | 20 Sep → 22 Sep with the conflict marked. |
| 1:55-2:35 | AWS | Architecture diagram; one sentence per service and **why**. The CloudWatch log line for the request just made (request ID). Cost guardrails: limits, one model call per question, budget alert. |
| 2:35-2:50 | Engineering proof | Eval results table (measured values only); the deterministic conflict predicate in one sentence. |
| 2:50-3:00 | Impact | "See the conflict, the sources and the reason in one place." End on the conflict inspector. |

Optional, only if M5 is stable: replace 2:35-2:50 with the workflow suggestion card.

## 5. Writeup outline (`docs/WRITEUP.md`, drafted by `/release`)
Problem and who has it · what we built · how it works (the evidence pipeline, the deterministic
conflict predicate) · where AWS fits (each service, the decision behind it, cost) · what was hard ·
what we learned (a judged criterion; from the Learning log) · limitations · what's next · AI coding tools used (Claude Code with Claude Opus 5, and any others) ·
third-party credits.

## 6. Submission checklist
**Required**
- [ ] Public repository; history starts inside the event window; no force-pushes
- [ ] Video of three minutes or less showing every claimed feature, and AWS visibly used
- [ ] Writeup: problem, build, AWS usage, AI tools named
- [ ] Every member checked in to First Commit on its page
- [ ] Submitted through First Commit's form before the deadline (early, then edited as needed)

**Product**
- [ ] Golden path works on the deployed URL from a clean browser
- [ ] Seeded demo documents in the repo (`demo/`) or documented
- [ ] Known limitations listed

**Repository quality**
- [ ] README: problem, screenshots or GIF, architecture diagram, AWS services and why, setup, demo
  steps, limitations
- [ ] `CREDITS.md`: AI tools, open-source components with licences, design skills
- [ ] No secrets (gitleaks clean); no unnecessary features

**Honesty**
- [ ] No invented benchmark numbers; unmeasured values say "not measured"
- [ ] No claim in the writeup that the video doesn't show

**Optional**
- [ ] Blog post on AWS Builder Center (the top five win a prize), linked in the submission
- [ ] Build It is considered automatically; document a local run (SAM Local + OpenSearch in Docker)
  if the stack supports it
