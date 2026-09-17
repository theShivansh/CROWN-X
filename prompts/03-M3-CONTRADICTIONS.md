# 03 · M3 · Contradiction engine and conflict inspector

Build the reason CROWN-X exists. When two documents give different values for the same fact, the
product shows both values, where each came from, which one is current and by what rule. This happens
live on the deployed URL, in a conflict inspector good enough to anchor the video and the Best UI
entry.

The design constraint that shapes everything here: **a false conflict on screen does more damage than
a missed one.** A user who sees "Sources disagree" about two values that are the same stops trusting
the product. So a model may help read claims out of text, but deterministic, tested code normalizes
values and decides whether two claims conflict (ADR-003).

## Read first
- `CLAUDE.md`
- `docs/MILESTONES.md` (M3)
- `docs/ARCHITECTURE.md` §4 (the contradiction contract)
- `docs/SRS.md` (Claim, Conflict, FR-07, FR-08)
- `docs/UI_UX.md` §§3.3, 3.5
- `docs/DESIGN.md` (all)
- `.claude/skills/rag-evidence/SKILL.md` and `.claude/skills/crown-ui/SKILL.md`, with its references
- `demo/SCENARIO.md`
- ADR-003 in `docs/DECISIONS.md`
- the M2 code

## 1. Claim extraction (at ingestion)
Claims are extracted once per document, after indexing. Conflicts and the M4 timeline need the whole
workspace's claims, not just what one question retrieved.

**The model's role.** One Bedrock call per document, over its chunks in batches that fit the model's
limits comfortably. Through a `submit_claims` tool schema, it returns candidate claims:
- `subject`, `attribute`
- `raw_value`, exactly as written
- `value_type`: `date` | `number` | `owner` | `category`
- `chunk_id`
- `quote`: the shortest verbatim span containing the value

Its system prompt is a reviewed file beside the answer prompt. It explains that the task is
extraction, not interpretation, and that document text is data.

**Code checks every candidate before it becomes a claim:**
- The `quote` must be a verbatim substring of that chunk's text, and `raw_value` must appear inside the
  quote. Otherwise the candidate is discarded and logged. This stops the model inventing a value the
  document doesn't contain.
- `subject` and `attribute` are canonicalized through `domain/vocabulary.py`: a small, explicit synonym
  map for the demo domain. For example, "deadline", "due date", "submission closes" and "submissions
  close" all map to `submission` / `deadline`; add rate limit, budget cap and deployment owner the same
  way. Anything unmapped keeps a slugified key and is only ever compared with an identical slug.

**Normalization** (`domain/normalize.py`, all deterministic):
- **Dates:** parse with explicit formats and month names. Infer a missing year only from the document's
  own `source_timestamp`. Treat an all-numeric date whose day and month are both ≤ 12 as ambiguous: it
  stays unnormalized, so it can't conflict. Normalized form: ISO date.
- **Numbers:** `Decimal` value plus a canonical unit from a unit table (`rpm` = "requests per
  minute" = "req/min"; ₹ = INR = rupees; MB; %). Values with different units that don't convert are
  incomparable.
- **Owners:** casefold, strip honorifics, collapse whitespace.
- **Categories:** casefold plus the synonym map.

Store claims as `CLAIM#{subject}#{attribute}#{claim_id}` with the SRS §4 fields plus `quote` and
`normalized_value`.

## 2. Conflict detection
`domain/conflicts.py` is a pure function over the claims for one `(subject, attribute)` key.

**The predicate.** A conflict exists between two claims when all of these hold:
- same canonical key;
- same `value_type`;
- both normalized;
- from different documents;
- normalized values differ.

"Differ" means: different ISO dates; different `Decimal` values in the same unit; different
normalized owner or category strings.

**Conflict records:**
- **ID:** a hash of the two sorted claim IDs, so recomputation is idempotent.
- **Type and severity:** `high` for dates and numbers on the configured critical attributes
  (deadline, budget cap, rate limit); `medium` otherwise.
- **Several differing values:** create pairwise conflicts, but the UI groups them by key.

**Selection** (`domain/selection.py`, FR-08). This chooses the current value and names the rule it
used:
1. `newest_source_timestamp`, when every claim on the key has a timestamp;
2. `version_order`, when the documents share a family and have parseable labels (v1 < v2,
   draft < final);
3. `latest_upload`, the weakest rule, named as such in the UI;
4. no selection, when none apply.

When claims agree on a value, the newest one decides nothing: selection only matters when values
differ.

**Recomputation.** After each document's claims are stored, recompute conflicts for the keys that
document touched. Delete conflicts whose claims no longer differ, for example when a document is
re-ingested.

## 3. Conflicts in the query flow
- `POST /query` now returns the conflicts where at least one claim's `chunk_id` is in the retrieved
  set, each with both claims, their evidence (including the other side, even if that chunk ranked
  lower), the selection and its rule. Relevance is decided by that ID intersection, not by the model.
- When conflicts are present, the answer call receives them as structured context. It must describe
  the disagreement rather than silently picking a value, and the final status is `conflict`. The
  conflict card renders from data, never from the answer text, so the product stays correct even if
  the model words it badly.
- `GET /workspaces/{ws}/conflicts` lists every conflict with both claims and the selection.

## 4. Conflict inspector (UI)
Run the crown-ui workflow, or `prompts/07-UI-SCREEN-PASS.md` with "conflict inspector", for this
screen and the answer card's conflict state. Build to `docs/UI_UX.md` §3.5:
- two columns, older left and newer right;
- the normalized values in Geist Mono with tabular figures;
- quoted spans with the value highlighted;
- source name, version and date on each side, with the `[Newer]` marker from the selection;
- the rule sentence;
- "Open source A / B";
- keyboard reachable.

Components from `.claude/skills/crown-ui/references/COMPONENTS.md`, adapted per its checklist:
- `border-beam`: only while the query's comparison stage is running;
- `morphing-disclosure`: for "Why was this flagged?", showing both normalized claims and the predicate
  in plain words.

State colours and icons come only from DESIGN §7.

## 5. Evaluation
Add or complete the conflict cases in the golden set: date, number and owner conflicts; format
equivalents (must not conflict); ambiguous numeric dates; the undated document's fallback; the
distractor. Run the eval. Record contradiction precision and recall, temporal selection accuracy, and
the change in every metric from the M2 baseline, in `docs/BENCHMARKS.md`. Precision below the proposed
gate blocks the milestone.

## 6. A rough demo recording
Record the golden path on the deployed URL (screen capture is fine) as it stands. Store the file
outside the repository and record its location in PROGRESS. Friday's recording is the insurance
policy if Saturday goes badly.

## Tests this milestone needs
**Unit:**
- normalization per type, including "22 Sept" = "2026-09-22", "60 rpm" = "60 requests per
  minute", ₹50,000 = "INR 50000", and `09/10/2026` treated as ambiguous;
- quote grounding rejects a value not in the chunk;
- the predicate: equal values in different formats never conflict; the same document never conflicts
  with itself;
- selection: each rule, and no selection without an ordering signal;
- conflict IDs are stable across recomputation;
- re-ingesting a document removes stale conflicts.

**API:** the query returns conflicts only when a participating chunk was retrieved; the answer status
is `conflict` when conflicts are present.

**Integration:** after uploading the demo corpus, exactly the scenario's conflicts exist, with no
extra ones.

## Out of scope
The timeline UI and API, requirement-text conflicts (list as a limitation), motion beyond the beam and
disclosure, the landing page, and workflow learning.

## Kill criterion
If model-assisted extraction of owners or categories isn't reliable on the demo corpus by Friday
evening, restrict the demo to dates and numbers, which the normalizers handle deterministically. List
the rest as a limitation in the README and an ADR; don't spend Saturday on it.

## Done means
- [ ] Date, numeric and owner conflicts detected; format-only differences never conflict (unit)
- [ ] Selection picks the newer source and names the rule; no selection without a signal (unit)
- [ ] Exactly the scenario's conflicts exist after ingesting the demo corpus (integration)
- [ ] Contradiction precision and recall recorded against the golden set (integration)
- [ ] The deadline conflict shown in the inspector with both passages on the deployed URL (live)
- [ ] Rough demo recording made

## Finish
- Update PROGRESS: the M3 row, the next-session line pointing at M4, the recording's location, and the
  verification log.
- Update `docs/SRS.md` and `docs/ARCHITECTURE.md` if the implementation refined a contract.
- Commit by path and push.
- Report:
  - precision and recall as measured;
  - any conflict type cut;
  - the three weakest spots in the demo path as it stands.
