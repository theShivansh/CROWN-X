import { describe, expect, it } from "vitest";

import { WorkflowSuggestionSchema } from "./api";
import { uuid7 } from "./events";
import { confidenceSentence, lastSeen, stepLabel, supportSentence, whyDetected } from "./workflows";

const suggestion = WorkflowSuggestionSchema.parse({
  suggestion_id: "wf_1",
  name: "Prepare sprint review",
  rule_name: "Ask a question → Read the answer → Inspect a conflict",
  description: "Check the deadline conflict and share the answer.",
  named_by: "openai/gpt-oss-120b",
  steps: ["ask_question", "read_answer", "inspect_conflict", "open_timeline", "copy_answer"],
  support: 3,
  recency: "2026-09-19T14:05:00.000000Z",
  confidence: 0.75,
  first_step_count: 4,
  traces: [["a"], ["b"], ["c"]],
  trace_sessions: ["ses_1", "ses_1", "ses_2"],
  trace_times: [["2026-09-19T14:00:00Z"], ["2026-09-19T14:02:00Z"], ["2026-09-19T14:05:00Z"]],
  example_session_ids: ["ses_2", "ses_1"],
  saved_versions: [],
});

describe("workflow card copy", () => {
  it("says the confidence as counts, never a percentage", () => {
    expect(confidenceSentence(suggestion)).toBe('Finished 3 of the 4 times it started with "ask a question".');
    expect(whyDetected(suggestion).join(" ")).not.toMatch(/%|0\.75/);
    expect(whyDetected(suggestion).at(-1)).toMatch(/a model only suggested the name/);
    expect(whyDetected({ ...suggestion, named_by: "rule" }).at(-1)).toMatch(/No model was used/);
  });

  it("counts sessions and names each step", () => {
    expect(supportSentence(suggestion)).toBe("Seen 3 times, in 2 sessions.");
    expect(stepLabel("inspect_conflict")).toBe("Inspect a conflict");
    expect(stepLabel("something_new")).toBe("something new");
  });

  it("shows only the time for today", () => {
    const now = new Date("2026-09-19T15:00:00Z");
    expect(lastSeen("2026-09-19T14:05:00Z", now)).toMatch(/^\d{2}:\d{2}$/);
    expect(lastSeen("2026-09-17T14:05:00Z", now)).toMatch(/Sep/);
  });
});

describe("uuid7", () => {
  it("is a version 7, variant 10 UUID whose first 48 bits are the time", () => {
    const id = uuid7(0x0192_0a3b_4c5d, new Uint8Array(10).fill(0xff));
    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(id.startsWith("01920a3b-4c5d-7")).toBe(true);
  });
});
