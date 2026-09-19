import type { Page, Route } from "@playwright/test";

import answerDeadline from "./fixtures/answer-deadline.json";
import answerInsufficient from "./fixtures/answer-insufficient.json";
import conflicts from "./fixtures/conflicts.json";
import documents from "./fixtures/documents.json";
import health from "./fixtures/health.json";
import queryDeadline from "./fixtures/query-deadline.json";
import queryInsufficient from "./fixtures/query-insufficient.json";
import timelineDeadline from "./fixtures/timeline-deadline.json";
import eventRecorded from "./fixtures/event-recorded.json";
import workflowSaved from "./fixtures/workflow-saved.json";
import workflowsAfterSave from "./fixtures/workflows-after-save.json";
import workflowsEmpty from "./fixtures/workflows-empty.json";
import workflowsRefresh from "./fixtures/workflows-refresh.json";

/** The workspace the recorded fixtures came from (a local API run over the real resolver). */
export const WORKSPACE = "ws_iWnb7m2xqxxFlGRxfBrrJg";
export const API = "http://api.e2e.test";

type Fixture = { status: number; body: unknown };
export type Overrides = Partial<
  Record<"documents" | "query" | "answer" | "timeline" | "workflows" | "refresh", Fixture | Fixture[]>
>;

/** The SRS §6 error envelope, as the API sends it. */
export function apiError(status: number, code: string, message: string, requestId: string): Fixture {
  return { status, body: { error: { code, message, request_id: requestId } } };
}

/**
 * Answers every API call from the fixtures. An override that is a list is used one response per
 * call, the last one repeating: `[timeout, success]` fails once, then succeeds on Retry.
 */
export async function mockApi(page: Page, overrides: Overrides = {}) {
  const calls: string[] = [];
  const queues = new Map(Object.entries(overrides).map(([k, v]) => [k, Array.isArray(v) ? [...v] : [v]]));
  const next = (name: keyof Overrides, fallback: Fixture): Fixture => {
    const queue = queues.get(name);
    if (!queue?.length) return fallback;
    return queue.length > 1 ? queue.shift()! : queue[0];
  };
  const question = (route: Route) => (JSON.parse(route.request().postData() ?? "{}").question ?? "") as string;

  await page.route(`${API}/**`, async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    calls.push(`${route.request().method()} ${path}`);
    let fixture: Fixture;
    if (path === "/health") fixture = health;
    else if (path.endsWith("/documents")) fixture = next("documents", documents);
    else if (path.endsWith("/conflicts")) fixture = conflicts;
    else if (path.endsWith("/timeline")) fixture = next("timeline", timelineDeadline);
    // Workflow Learning Lite (built with NEXT_PUBLIC_WORKFLOWS_ENABLED=true): none until refreshed.
    else if (path.endsWith("/events")) fixture = eventRecorded;
    else if (path.endsWith("/workflow-suggestions/refresh")) fixture = next("refresh", workflowsRefresh);
    else if (path.endsWith("/save")) fixture = workflowSaved;
    else if (path.endsWith("/workflow-suggestions"))
      fixture = next("workflows", calls.some((c) => c.endsWith("/save")) ? workflowsAfterSave : workflowsEmpty);
    else if (path.endsWith("/query"))
      fixture = next("query", /deadline/i.test(question(route)) ? queryDeadline : queryInsufficient);
    else if (path.endsWith("/answer"))
      fixture = next("answer", path.includes(queryDeadline.body.query_id) ? answerDeadline : answerInsufficient);
    else fixture = apiError(404, "not_found", "Not found.", "req_e2e_404");
    await route.fulfill({
      status: fixture.status,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*", "access-control-expose-headers": "x-request-id" },
      body: JSON.stringify(fixture.body),
    });
  });
  return calls;
}
