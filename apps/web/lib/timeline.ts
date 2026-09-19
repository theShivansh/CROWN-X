/**
 * How a value timeline reads (UI_UX §3.6). Pure functions over `/timeline`, tested, so the track
 * never infers anything the API didn't say.
 */
import type { Timeline, TimelineEvent } from "./api";
import { displayValue, formatDate, ruleName, timelineOrder } from "./conflicts";

/** "10 Sep 2026", or the API's own label for an undated source ("undated · uploaded 2nd"). */
export function eventDate(event: TimelineEvent): string {
  return event.source_timestamp ? formatDate(event.source_timestamp) : event.order_label;
}

export function eventValue(timeline: Pick<Timeline, "type">, event: TimelineEvent): string {
  return displayValue({ ...event, value_type: timeline.type });
}

/**
 * The segment between event i-1 and event i is a conflict when the two events share a conflict ID:
 * the predicate paired exactly those two sources. A change of unit alone isn't one.
 */
export function conflictSegments(events: TimelineEvent[]): boolean[] {
  return events.map((event, i) => {
    if (i === 0) return false;
    const before = new Set(events[i - 1].conflict_ids);
    return event.conflict_ids.some((id) => before.has(id));
  });
}

/** What changed, in one line: "20 Sep 2026 → 22 Sep 2026, 1 change across 3 sources". */
export function timelineSummary(timeline: Timeline): string {
  const { events } = timeline;
  if (events.length === 0) return "No source in this workspace states this value yet.";
  const changes = events.filter((e) => e.changed).length;
  const values: string[] = [];
  for (const event of events) {
    const value = eventValue(timeline, event);
    if (values[values.length - 1] !== value) values.push(value);
  }
  const sources = `${events.length} ${events.length === 1 ? "source" : "sources"}`;
  if (changes === 0) return `${values[0]} in every source (${sources}).`;
  return `${values.join(" → ")}: ${changes} ${changes === 1 ? "change" : "changes"} across ${sources}.`;
}

/** The index the arrow keys move to; Home and End jump to the ends. */
export function nextIndex(key: string, current: number, count: number): number | null {
  if (count === 0) return null;
  switch (key) {
    case "ArrowRight":
    case "ArrowDown":
      return Math.min(current + 1, count - 1);
    case "ArrowLeft":
    case "ArrowUp":
      return Math.max(current - 1, 0);
    case "Home":
      return 0;
    case "End":
      return count - 1;
    default:
      return null;
  }
}

/** The order, then the current value and the rule that chose it (the inspector's own words). */
export function timelineRule(timeline: Timeline): string {
  const order = timelineOrder({ selection_rule: timeline.selection_rule });
  const selected = timeline.events.find((e) => e.selected);
  if (!selected || !timeline.selection_rule) return `${order} No current value is chosen.`;
  return `${order} Current value: ${eventValue(timeline, selected)}, rule: ${ruleName(timeline.selection_rule)}.`;
}
