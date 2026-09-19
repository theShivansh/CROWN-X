import { expect, test, type Page } from "@playwright/test";

import answerDeadline from "./fixtures/answer-deadline.json";
import documentsWithFailure from "./fixtures/documents-with-failure.json";
import { WORKSPACE, apiError, mockApi } from "./mock-api";

/**
 * The golden path and the main failure states (M4 §5), tagged @critical. Against the static build
 * with recorded responses by default; with E2E_BASE_URL (and E2E_WORKSPACE) the golden path runs
 * against the deployed site and its real API instead.
 */
const live = Boolean(process.env.E2E_BASE_URL);
const workspace = live ? process.env.E2E_WORKSPACE ?? "" : WORKSPACE;
const GOLDEN = "What is the current submission deadline?";

async function askWithPalette(page: Page, question: string) {
  await page.keyboard.press("ControlOrMeta+k");
  const palette = page.getByRole("dialog", { name: "Ask CROWN" });
  await expect(palette).toBeVisible();
  await palette.getByRole("combobox", { name: "Question" }).fill(question);
  await page.keyboard.press("Enter");
  await expect(palette).toBeHidden();
}

test.describe("@critical", () => {
  test.beforeEach(() => {
    test.skip(live && !workspace, "set E2E_WORKSPACE to the demo workspace ID for the live run");
  });

  test("golden path: ask, see the conflict, inspect it, follow the timeline", async ({ page }) => {
    if (!live) await mockApi(page);
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));

    await page.goto(`/app/?ws=${workspace}`);
    await expect(page.getByText(/documents? indexed/)).toBeVisible();
    await askWithPalette(page, GOLDEN);

    const answer = page.getByRole("region", { name: "Answer" });
    await expect(answer.getByText("Sources disagree")).toBeVisible();
    await expect(answer.getByText(/rule: newest source date/)).toBeVisible();

    // The conflict card sits among the evidence, and the inspector names both sources.
    const evidence = page.getByRole("complementary", { name: "Evidence" });
    await expect(evidence.getByText("Sources disagree on the submission deadline")).toBeVisible();
    const inspector = page.getByRole("region", { name: /Date conflict on submission deadline/ });
    await expect(inspector.getByText("project-brief-v1.pdf").first()).toBeVisible();
    await expect(inspector.getByText(/Newer · 10 Sep/)).toBeVisible();

    // A citation chip opens its passage.
    await answer.getByRole("button", { name: /^Open evidence \d+$/ }).first().click();
    await expect(page.locator("[id^=evidence-ev_]:focus")).toBeVisible();

    // The timeline: the change, marked, and the arrow keys step through the sources.
    await inspector.getByRole("button", { name: "Open the full timeline" }).click();
    const timeline = page.getByRole("region", { name: /Timeline · submission deadline/ });
    await expect(timeline.getByText(/20 Sep 2026 → 22 Sep 2026: 1 change across 3 sources/)).toBeVisible();
    const steps = timeline.getByRole("list", { name: /How the submission deadline changed/ });
    await expect(steps.getByRole("button", { name: /value changed, conflicts with the previous source/ })).toBeVisible();
    await steps.getByRole("button", { name: /current value/ }).focus();
    await page.keyboard.press("ArrowLeft");
    await expect(steps.getByRole("button", { name: /value changed/ })).toBeFocused();

    expect(errors).toEqual([]);
  });

  test("a question the documents can't answer says so and names what was searched", async ({ page }) => {
    test.skip(live, "recorded-response test");
    await mockApi(page);
    await page.goto(`/app/?ws=${workspace}`);
    await askWithPalette(page, "What colour is the FestPass logo?");
    const answer = page.getByRole("region", { name: "Answer" });
    await expect(answer.getByText("Not enough evidence", { exact: true })).toBeVisible();
    await expect(answer.getByText(/passages were searched/)).toBeVisible();
  });

  test("an answer that times out shows the request ID, and Retry answers", async ({ page }) => {
    test.skip(live, "recorded-response test");
    const timeout = apiError(
      504,
      "model_timeout",
      "The answer model didn't respond in time. Retry; the evidence is kept.",
      "req_e2e_timeout",
    );
    const calls = await mockApi(page, { answer: [timeout, answerDeadline] });
    await page.goto(`/app/?ws=${workspace}`);
    await askWithPalette(page, GOLDEN);

    const answer = page.getByRole("region", { name: "Answer" });
    await expect(answer.getByRole("alert")).toContainText("didn't respond in time");
    await expect(answer.getByText("req_e2e_timeout")).toBeVisible();
    await answer.getByRole("button", { name: "Retry the answer" }).click();
    await expect(answer.getByText("Sources disagree")).toBeVisible();
    // Retry answers over the same stored evidence: one query, two answer calls.
    expect(calls.filter((c) => c.endsWith("/query"))).toHaveLength(1);
    expect(calls.filter((c) => c.endsWith("/answer"))).toHaveLength(2);
  });

  test("over the hourly limit, the question is refused with the reason and request ID", async ({ page }) => {
    test.skip(live, "recorded-response test");
    await mockApi(page, {
      query: apiError(429, "limit_reached", "This workspace has used its 60 questions for this hour. Try again in 12 minutes.", "req_e2e_limit"),
    });
    await page.goto(`/app/?ws=${workspace}`);
    await askWithPalette(page, GOLDEN);
    const answer = page.getByRole("region", { name: "Answer" });
    await expect(answer.getByRole("alert")).toContainText("60 questions for this hour");
    await expect(answer.getByText("req_e2e_limit")).toBeVisible();
  });

  test("a scanned PDF fails ingestion with the reason and what to do", async ({ page }) => {
    test.skip(live, "recorded-response test");
    await mockApi(page, { documents: documentsWithFailure });
    await page.goto(`/app/?ws=${workspace}`);
    const rail = page.getByRole("navigation", { name: "Documents" });
    await expect(rail.getByText("scan.pdf")).toBeVisible();
    await expect(rail.getByText("Ingestion failed")).toBeVisible();
    await expect(rail.getByText(/No text found; upload a text PDF/)).toBeVisible();
  });
});


test.describe("@critical reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("with reduced motion, evidence and the conflict card appear in their final state", async ({ page }) => {
    test.skip(live, "recorded-response test");
    await mockApi(page);
    await page.goto(`/app/?ws=${workspace}`);
    await askWithPalette(page, GOLDEN);
    const evidence = page.getByRole("complementary", { name: "Evidence" });
    const card = evidence.getByText("Sources disagree on the submission deadline");
    await expect(card).toBeVisible();
    // Nothing is mid-entrance: every item in the list is fully opaque at once.
    const opacities = await evidence
      .locator("ol > li")
      .evaluateAll((items) => items.map((item) => getComputedStyle(item).opacity));
    expect(opacities.length).toBeGreaterThan(1);
    expect(new Set(opacities)).toEqual(new Set(["1"]));
  });
});
