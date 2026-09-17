# CROWN-X UI and UX specification

Visual rules: `docs/DESIGN.md`. This file covers screens, flows and states.

## 1. Principles
1. Never hide uncertainty. "Sources disagree" and "Not enough evidence" are first-class answers.
2. Every factual answer shows its evidence, and every piece of evidence opens to its passage.
3. No number without a definition. There is no confidence score in the hackathon UI (CLAUDE.md
   rule 10); support counts ("3 sources") are fine because they are exact.
4. Errors say what failed and what to do next.
5. The golden demo path fits one screen, with no navigation gymnastics.

## 2. The golden demo path (what the video shows)
1. Workspace with three seeded documents already uploaded (or uploaded live, stages visible).
2. ⌘K / Ctrl+K opens Ask. Type "What is the current submission deadline?"
3. Evidence cards arrive; the conflict card appears between "Project brief v1 · 20 Sep" and
   "Organiser update · 22 Sep".
4. The answer settles: "Sources disagree. The newer sources say 22 September…", with citation chips.
5. Click a chip; the evidence panel highlights the exact passage.
6. Open the timeline for `submission_deadline`: 20 Sep → 22 Sep, with the conflict marked.
7. (Only if M5 shipped and is stable) a workflow suggestion card, "Why detected?", save.

## 3. Screens

### 3.1 Workspace (app shell)
- **Left rail:** workspace name; document list (name, version, status dot and label, conflict count);
  upload button; saved workflows (M5).
- **Centre:** Ask bar at the top (also ⌘K); conversation of question/answer cards, newest first.
- **Right:** evidence panel for the selected answer: evidence cards, conflict cards, timeline link.
- **Header:** counters (documents indexed, conflicts found) with `animated-number` on change only.
- **Empty state:** "Upload two or more versions of a project document to see where they disagree."
  Upload action, and the accepted types and size limit.

### 3.2 Document ingestion
- Drop zone plus file picker. PDF, TXT, MD; limits from SRS.
- One card per file, each resolving on its own: `Uploading` → `Parsing` → `Indexing` → `Ready`
  (chunk count) or `Failed` (reason and action: "Scanned PDF has no text. Upload a text PDF.").
- Duplicate upload: "Already indexed as brief-v2.pdf", linking to it.

### 3.3 Answer card
States:
- **Grounded:** answer text, `SealCheck` "Supported by N sources", citation chips `[1] [2]`.
- **Conflict:** `GitDiff` "Sources disagree", a one-line summary of both values, the selected value and
  the rule used ("newest source date"), link to the inspector.
- **Partial:** supported sentences have chips; unsupported ones are removed, not shown greyed.
- **Insufficient evidence:** `Question` "Not enough evidence", what was searched, a suggestion.
- **Error:** what failed (retrieval, model), request ID in mono, Retry.
- **Loading:** stage text from the API ("Retrieving evidence", "Comparing 2 sources",
  "Writing answer"), skeleton reserving the card's space.

### 3.4 Evidence card
Source name · version · date (mono, tabular) · page or section · the quoted span with the matched
value highlighted · "Open source". Keyboard: arrow keys move between cards, Enter opens.

### 3.5 Conflict inspector (the most important screen)
Two columns, older on the left and newer on the right:
```text
PROJECT BRIEF v1 · 20 SEP 2026            ORGANISER UPDATE · 22 SEP 2026   [Newer]
"Submissions close on 20 September"       "The deadline moves to 22 September"
value: 2026-09-20                          value: 2026-09-22
                    ── date conflict on submission_deadline ──
Why flagged: same subject and attribute, normalized dates differ.
Current value shown: 2026-09-22, rule: newest source date.        [Why was this flagged?]
[Open source A]                                                     [Open source B]
```
- The border beam runs on this card only while comparison is running.
- "Why was this flagged?" (morphing disclosure) shows the normalized claims and the predicate.

### 3.6 Timeline
Horizontal track for one subject/attribute. Each event: date, source, value, and a marker where the
value changed; a conflict segment is outlined in `--conflict`. Keyboard: arrow keys step through
events. Below 1024px it becomes a vertical list.

### 3.7 Workflow suggestion (M5, gated)
- **Card:** "Repeated workflow detected" · 4-7 compact nodes in order · badges: occurrences, last seen
  · Save workflow / Dismiss · "Why detected?".
- **Detail:** ordered steps on the left; the matching event traces with timestamps on the right; saved
  version at the bottom.
- One flow visualization, not a knowledge graph.

### 3.8 Landing page (optional, M4 if time)
One screen: headline (stagger-text), one sentence on the problem, a real screenshot or short loop of
the conflict inspector, "Open the demo workspace" CTA, and the AWS architecture strip. No feature-card
triplet, no testimonials, no pricing.

## 4. Responsive
Desktop-first (the video is recorded at 1440x900). At 1024 the evidence panel becomes a right sheet.
Below 768 panes stack: rail, then the conversation; evidence opens full screen. No horizontal scroll at
any width.

## 5. Accessibility
Semantic headings per pane; landmarks (`nav`, `main`, `aside`); visible focus; live region announcing
stage changes and "Answer ready"; no colour-only states; reduced motion honoured.
