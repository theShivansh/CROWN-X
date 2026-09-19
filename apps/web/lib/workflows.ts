/**
 * How a detected workflow reads (UI_UX §3.7). Every number on the card is a count with its meaning in
 * words (CLAUDE.md rule 10): never a bare percentage.
 */
import type { WorkflowSuggestion } from "./api";

export const STEP_LABELS: Record<string, string> = {
  add_document: "Add a document",
  ask_question: "Ask a question",
  read_answer: "Read the answer",
  open_evidence: "Open a cited passage",
  inspect_conflict: "Inspect a conflict",
  open_timeline: "Open the timeline",
  copy_answer: "Copy the answer",
};

export function stepLabel(step: string): string {
  return STEP_LABELS[step] ?? step.replaceAll("_", " ");
}

export function timesLabel(count: number): string {
  return count === 1 ? "once" : count === 2 ? "twice" : `${count} times`;
}

/** The confidence in words: how often starting this way led to the whole sequence. */
export function confidenceSentence(s: Pick<WorkflowSuggestion, "support" | "first_step_count" | "steps">): string {
  const first = stepLabel(s.steps[0]).toLowerCase();
  return `Finished ${s.support} of the ${s.first_step_count} times it started with "${first}".`;
}

/** "Seen 3 times, in 1 session" (sessions end after 30 minutes without activity). */
export function supportSentence(s: Pick<WorkflowSuggestion, "support" | "trace_sessions">): string {
  const sessions = new Set(s.trace_sessions).size;
  return `Seen ${timesLabel(s.support)}, in ${sessions} ${sessions === 1 ? "session" : "sessions"}.`;
}

/** "14:05" today, else "18 Sep 14:05": when the sequence last finished, in the viewer's time zone. */
export function lastSeen(iso: string, now: Date = new Date()): string {
  const at = new Date(iso);
  const time = at.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  if (at.toDateString() === now.toDateString()) return time;
  return `${at.toLocaleDateString("en-GB", { day: "numeric", month: "short" })} ${time}`;
}

/** Why code found it, in plain words, for the "Why detected?" panel. */
export function whyDetected(s: WorkflowSuggestion): string[] {
  return [
    `The same ${s.steps.length} steps happened in this order ${timesLabel(s.support)}, with nothing in between.`,
    supportSentence(s),
    confidenceSentence(s),
    s.named_by === "rule"
      ? "Found by counting your workspace's own actions. No model was used. Nothing runs automatically."
      : "Found by counting your workspace's own actions; a model only suggested the name. Nothing runs automatically.",
  ];
}

/** The suggestion to show on the card: the one seen most, then the longest (the API's own order). */
export function topSuggestion(suggestions: WorkflowSuggestion[]): WorkflowSuggestion | null {
  return suggestions[0] ?? null;
}
