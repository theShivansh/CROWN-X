/**
 * How a conflict reads on screen (UI_UX §3.3, §3.5). Pure functions over the API's conflict groups, so
 * every sentence the inspector shows is built from data and tested, never taken from answer text.
 */
import type { Claim, ConflictGroup, SelectionRule } from "./api";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-09-22" as "22 Sep 2026" (no time zone: it is a calendar date). */
export function formatDate(iso: string, withYear = true): string {
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return iso;
  return `${day} ${MONTHS[month - 1]}${withYear ? ` ${year}` : ""}`;
}

const UNIT_WORDS: Record<string, string> = {
  requests_per_minute: "per minute",
  requests_per_second: "per second",
  percent: "%",
};

function groupDigits(value: string, indian: boolean): string {
  const [whole, fraction] = value.split(".");
  const formatted = Number(whole).toLocaleString(indian ? "en-IN" : "en-US");
  return fraction ? `${formatted}.${fraction}` : formatted;
}

/** A value as people write it: 22 Sep 2026, ₹45,000, 60 per minute, Ishita Rao. */
export function displayValue(
  claim: Pick<Claim, "value_type" | "normalized_value" | "unit" | "raw_value">,
): string {
  const value = claim.normalized_value;
  if (value === null) return claim.raw_value;
  if (claim.value_type === "date") return formatDate(value);
  if (claim.value_type === "owner") return claim.raw_value.replace(/\s+/g, " ").trim();
  if (claim.unit === "INR") return `₹${groupDigits(value, true)}`;
  const words = claim.unit ? (UNIT_WORDS[claim.unit] ?? claim.unit) : "";
  return words ? `${groupDigits(value, false)} ${words}` : groupDigits(value, false);
}

/** The normalized form the predicate compared: `2026-09-22`, `45000 INR`, `60 requests_per_minute`. */
export function normalizedValue(claim: Pick<Claim, "normalized_value" | "unit">): string {
  if (claim.normalized_value === null) return "not normalized";
  return claim.unit ? `${claim.normalized_value} ${claim.unit}` : claim.normalized_value;
}

/** "project-brief-v1.pdf" as "project-brief-v1.pdf · v1", and its date or "undated". */
export function sourceLine(claim: Claim): { name: string; version: string | null; date: string } {
  return {
    name: claim.filename,
    version: claim.version_label ?? null,
    date: claim.source_timestamp ? formatDate(claim.source_timestamp) : "undated",
  };
}

export function claimById(group: ConflictGroup, claimId: string): Claim {
  const found = group.claims.find((c) => c.claim_id === claimId);
  if (!found) throw new Error(`conflict ${group.key} has no claim ${claimId}`);
  return found;
}

/** The pair the inspector opens on (the API chooses it): older on the left, newer on the right. */
export function primaryPair(group: ConflictGroup): { older: Claim; newer: Claim } {
  const pair = group.pairs.find((p) => p.conflict_id === group.primary_conflict_id) ?? group.pairs[0];
  return { older: claimById(group, pair.claim_a), newer: claimById(group, pair.claim_b) };
}

export function selectedClaim(group: ConflictGroup): Claim | null {
  return group.selected_claim_id ? claimById(group, group.selected_claim_id) : null;
}

const RULE_NAMES: Record<SelectionRule, string> = {
  newest_source_timestamp: "newest source date",
  version_order: "document version order",
  latest_upload: "latest upload",
};

export function ruleName(rule: SelectionRule | null): string {
  return rule ? RULE_NAMES[rule] : "none";
}

/** The rule sentence under the columns. `latest_upload` is always named as the weakest rule. */
export function ruleSentence(group: ConflictGroup): string {
  const selected = selectedClaim(group);
  if (!selected || !group.selection_rule) {
    return "No current value: these sources have no dates, versions or upload order to decide between them.";
  }
  const shown = `Current value shown: ${displayValue(selected)}, rule: ${ruleName(group.selection_rule)}.`;
  if (group.selection_rule === "latest_upload") {
    return `${shown} This is the weakest rule: at least one source has no date, so the file uploaded last wins.`;
  }
  return shown;
}

/** One line for the answer card: each distinct value with the first source that states it. */
export function conflictSummary(group: ConflictGroup): string {
  const seen = new Map<string, Claim>();
  for (const claim of group.claims) {
    const key = normalizedValue(claim);
    if (!seen.has(key)) seen.set(key, claim);
  }
  return [...seen.values()]
    .map((c) => `${c.filename} says ${displayValue(c)}`)
    .join("; ");
}

export type TimelinePoint = {
  claim: Claim;
  label: string; // the date, the version, or "undated"
  changed: boolean; // the value differs from the previous point
  selected: boolean;
};

/**
 * Every claim on the fact, in the order the selection rule uses (the API sends them in that order),
 * with value changes marked: brief v1 → update 3 (changed) → Sync 5 (no change) → selected.
 */
export function timeline(group: ConflictGroup): TimelinePoint[] {
  return group.claims.map((claim, index) => {
    const previous = index > 0 ? group.claims[index - 1] : null;
    return {
      claim,
      label: claim.source_timestamp
        ? formatDate(claim.source_timestamp)
        : (claim.version_label ?? "undated"),
      changed: previous !== null && normalizedValue(previous) !== normalizedValue(claim),
      selected: claim.claim_id === group.selected_claim_id,
    };
  });
}

/** How the timeline is ordered, in words: which signal placed the points. */
export function timelineOrder(group: Pick<ConflictGroup, "selection_rule">): string {
  switch (group.selection_rule) {
    case "newest_source_timestamp":
      return "Ordered by each document's own date.";
    case "version_order":
      return "Ordered by document version.";
    case "latest_upload":
      return "Ordered by upload time, because at least one source has no date.";
    default:
      return "No order: nothing dates or versions these sources.";
  }
}

/** "Why was this flagged?": the predicate, in plain words, over the two claims. */
export function whyFlagged(group: ConflictGroup, older: Claim, newer: Claim): string[] {
  const how = (c: Claim) =>
    c.trigger_is_label ? `matched the label "${c.trigger}"` : `matched the phrase "${c.trigger}"`;
  return [
    `Same fact: both state the ${group.label} (${group.subject} / ${group.attribute}).`,
    `Same kind of value: ${group.type === "number" ? "a number with its unit" : `a ${group.type}`}.`,
    `${older.filename} ${how(older)}; its value normalizes to ${normalizedValue(older)}.`,
    `${newer.filename} ${how(newer)}; its value normalizes to ${normalizedValue(newer)}.`,
    "They come from different documents and the normalized values differ, so code flagged a conflict. A model never decides this.",
  ];
}
