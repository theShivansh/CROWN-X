import { describe, expect, it } from "vitest";

import { TimelineResponse, type Timeline, type TimelineEvent } from "./api";
import { conflictSegments, eventDate, nextIndex, timelineRule, timelineSummary } from "./timeline";

function event(overrides: Partial<TimelineEvent>): TimelineEvent {
  return {
    claim_id: "cl_1",
    document_id: "doc_1",
    filename: "project-brief-v1.pdf",
    version_label: "v1",
    source_timestamp: "2026-08-31",
    uploaded_at: "2026-09-19T10:00:00Z",
    dated: true,
    order_label: "2026-08-31",
    raw_value: "20 September 2026",
    normalized_value: "2026-09-20",
    unit: null,
    quote: "Final submissions close on 20 September 2026",
    source_chunk_id: "doc_1:0",
    changed: false,
    conflict_ids: [],
    selected: false,
    ...overrides,
  };
}

const deadline: Timeline = TimelineResponse.parse({
  request_id: "req_1",
  key: "submission/deadline",
  subject: "submission",
  attribute: "deadline",
  label: "submission deadline",
  type: "date",
  selection_rule: "newest_source_timestamp",
  selected_claim_id: "cl_3",
  events: [
    event({ conflict_ids: ["cf_a", "cf_b"] }),
    event({
      claim_id: "cl_2",
      filename: "organiser-update-3.txt",
      source_timestamp: "2026-09-10",
      normalized_value: "2026-09-22",
      raw_value: "22 Sept",
      changed: true,
      conflict_ids: ["cf_a"],
    }),
    event({
      claim_id: "cl_3",
      filename: "meeting-notes-sync-5.md",
      source_timestamp: "2026-09-11",
      normalized_value: "2026-09-22",
      raw_value: "22 September 2026",
      conflict_ids: ["cf_b"],
      selected: true,
    }),
  ],
});

describe("value timeline", () => {
  it("summarises the values in order and counts only real changes", () => {
    expect(timelineSummary(deadline)).toBe("20 Sep 2026 → 22 Sep 2026: 1 change across 3 sources.");
  });

  it("outlines a segment only where the predicate paired its two sources", () => {
    expect(conflictSegments(deadline.events)).toEqual([false, true, false]);
  });

  it("dates an event by its source, and labels an undated one by upload position", () => {
    expect(eventDate(deadline.events[1])).toBe("10 Sep 2026");
    const undated = event({ source_timestamp: null, dated: false, order_label: "undated · uploaded 2nd" });
    expect(eventDate(undated)).toBe("undated · uploaded 2nd");
  });

  it("says so when every source agrees, and when none states the value", () => {
    expect(timelineSummary({ ...deadline, events: [deadline.events[0]] })).toBe("20 Sep 2026 in every source (1 source).");
    expect(timelineSummary({ ...deadline, events: [] })).toBe("No source in this workspace states this value yet.");
  });

  it("names the order, the current value and its rule", () => {
    expect(timelineRule(deadline)).toBe(
      "Ordered by each document's own date. Current value: 22 Sep 2026, rule: newest source date.",
    );
    expect(timelineRule({ ...deadline, selection_rule: null, events: deadline.events.map((e) => ({ ...e, selected: false })) })).toBe(
      "No order: nothing dates or versions these sources. No current value is chosen.",
    );
  });

  it("moves with the arrow keys and stops at the ends", () => {
    expect(nextIndex("ArrowRight", 2, 3)).toBe(2);
    expect(nextIndex("ArrowDown", 0, 3)).toBe(1);
    expect(nextIndex("ArrowLeft", 0, 3)).toBe(0);
    expect(nextIndex("End", 0, 3)).toBe(2);
    expect(nextIndex("Home", 2, 3)).toBe(0);
    expect(nextIndex("Enter", 1, 3)).toBeNull();
  });
});
