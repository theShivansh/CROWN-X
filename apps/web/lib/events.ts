/**
 * Workflow events from the browser (M5, ADR-022): what the user does in the UI, IDs only. Best effort:
 * a failed send never affects the page, and one retry reuses the same event ID, so the server records
 * it once. Nothing is sent unless NEXT_PUBLIC_WORKFLOWS_ENABLED is "true".
 */
import { api } from "./api";

export const WORKFLOWS_ENABLED = process.env.NEXT_PUBLIC_WORKFLOWS_ENABLED === "true";

export type ClientEventType = "evidence_opened" | "conflict_opened" | "timeline_opened" | "answer_copied";
export type EventRef = Partial<Record<"evidence_id" | "conflict_id" | "query_id" | "key" | "suggestion_id", string>>;

/** RFC 9562 UUIDv7: 48 bits of Unix milliseconds, then random bits, version 7, variant 10. */
export function uuid7(now: number = Date.now(), random: Uint8Array = crypto.getRandomValues(new Uint8Array(10))): string {
  const bytes = new Uint8Array(16);
  let ms = now;
  for (let i = 5; i >= 0; i--) {
    bytes[i] = ms % 256;
    ms = Math.floor(ms / 256);
  }
  bytes.set(random, 6);
  bytes[6] = 0x70 | (bytes[6] & 0x0f);
  bytes[8] = 0x80 | (bytes[8] & 0x3f);
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function track(workspaceId: string, eventType: ClientEventType, ref: EventRef = {}): void {
  if (!WORKFLOWS_ENABLED) return;
  const event = { event_id: uuid7(), event_type: eventType, occurred_at: new Date().toISOString(), ref };
  api.event(workspaceId, event).catch(() => {
    // One retry with the same ID; the server stores it once whichever attempt lands.
    window.setTimeout(() => void api.event(workspaceId, event).catch(() => undefined), 1500);
  });
}
