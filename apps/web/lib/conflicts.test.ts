import { describe, expect, it } from "vitest";

import { ConflictGroupSchema, type Claim, type ConflictGroup } from "./api";
import {
  conflictSummary,
  displayValue,
  formatDate,
  primaryPair,
  ruleSentence,
  timeline,
  timelineOrder,
  whyFlagged,
} from "./conflicts";

function claim(overrides: Partial<Claim>): Claim {
  return {
    claim_id: "cl_1",
    document_id: "doc_1",
    filename: "project-brief-v1.pdf",
    subject: "submission",
    attribute: "deadline",
    value_type: "date",
    raw_value: "20 September 2026",
    normalized_value: "2026-09-20",
    unit: null,
    quote: "submissions close on 20 September 2026",
    char_start: 0,
    char_end: 38,
    value_start: 21,
    value_end: 38,
    source_chunk_id: "doc_1:0",
    page_or_section: "Page 1",
    source_timestamp: "2026-08-31",
    version_label: "v1",
    uploaded_at: "2026-09-19T00:00:00Z",
    trigger: "submissions close",
    trigger_is_label: false,
    extraction_method: "rule",
    confidence: { extraction: 0.9 },
    ...overrides,
  };
}

// The deadline group as the API returns it for the demo corpus (SCENARIO §3, §8).
const brief = claim({});
const update = claim({
  claim_id: "cl_2",
  document_id: "doc_3",
  filename: "organiser-update-3.txt",
  raw_value: "22 Sept",
  normalized_value: "2026-09-22",
  source_timestamp: "2026-09-10",
  version_label: "update 3",
  trigger: "submission deadline",
  confidence: { extraction: 0.81 },
});
const sync = claim({
  claim_id: "cl_3",
  document_id: "doc_4",
  filename: "meeting-notes-sync-5.md",
  raw_value: "2026-09-22",
  normalized_value: "2026-09-22",
  source_timestamp: "2026-09-11",
  version_label: "Sync 5",
  trigger: "Deadline confirmed as",
});
const deadline: ConflictGroup = ConflictGroupSchema.parse({
  key: "submission/deadline",
  subject: "submission",
  attribute: "deadline",
  label: "submission deadline",
  type: "date",
  severity: "high",
  selection_rule: "newest_source_timestamp",
  selected_claim_id: "cl_3",
  selected_value: "2026-09-22",
  selected_unit: null,
  claims: [brief, update, sync],
  pairs: [
    { conflict_id: "cf_b", claim_a: "cl_1", claim_b: "cl_3", type: "date", severity: "high", status: "open" },
    { conflict_id: "cf_a", claim_a: "cl_1", claim_b: "cl_2", type: "date", severity: "high", status: "open" },
  ],
  primary_conflict_id: "cf_a",
});

describe("conflict view helpers", () => {
  it("formats values the way the documents write them", () => {
    expect(formatDate("2026-09-22")).toBe("22 Sep 2026");
    expect(displayValue(claim({ value_type: "number", normalized_value: "45000", unit: "INR" }))).toBe("₹45,000");
    expect(displayValue(claim({ value_type: "number", normalized_value: "100000", unit: "INR" }))).toBe("₹1,00,000");
    expect(
      displayValue(claim({ value_type: "number", normalized_value: "60", unit: "requests_per_minute" })),
    ).toBe("60 per minute");
    expect(displayValue(claim({ value_type: "owner", normalized_value: "ishita rao", raw_value: "Ishita Rao" }))).toBe(
      "Ishita Rao",
    );
  });

  it("opens on the primary pair: brief v1 against the organiser update", () => {
    const { older, newer } = primaryPair(deadline);
    expect([older.filename, newer.filename]).toEqual(["project-brief-v1.pdf", "organiser-update-3.txt"]);
  });

  it("names the rule, and calls latest upload the weakest", () => {
    expect(ruleSentence(deadline)).toBe("Current value shown: 22 Sep 2026, rule: newest source date.");
    const upload = { ...deadline, selection_rule: "latest_upload" as const };
    expect(ruleSentence(upload)).toContain("This is the weakest rule");
    const none = { ...deadline, selection_rule: null, selected_claim_id: null, selected_value: null };
    expect(ruleSentence(none)).toMatch(/^No current value/);
    expect(timelineOrder(none)).toMatch(/^No order/);
  });

  it("marks value changes on the timeline and the selected point", () => {
    const points = timeline(deadline);
    expect(points.map((p) => [p.label, p.changed, p.selected])).toEqual([
      ["31 Aug 2026", false, false],
      ["10 Sep 2026", true, false],
      ["11 Sep 2026", false, true], // same value as update 3: no change
    ]);
  });

  it("summarizes each distinct value once and explains the predicate", () => {
    expect(conflictSummary(deadline)).toBe(
      "project-brief-v1.pdf says 20 Sep 2026; organiser-update-3.txt says 22 Sep 2026",
    );
    const lines = whyFlagged(deadline, brief, update);
    expect(lines[2]).toBe('project-brief-v1.pdf matched the phrase "submissions close"; its value normalizes to 2026-09-20.');
    expect(lines.at(-1)).toContain("A model never decides this.");
  });

  it("rejects a conflict without two claims", () => {
    expect(ConflictGroupSchema.safeParse({ ...deadline, claims: [brief] }).success).toBe(false);
  });
});
