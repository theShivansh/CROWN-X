// Captures the README screenshots and the GIF frames from the deployed app (docs/media/README_ASSETS.md).
// Not a test: it asks one real question, so it makes one Groq call and adds events to the demo workspace.
// Run from apps/web: node e2e/capture-media.mjs <out-dir>   (HTTPS_PROXY is used when it is set)
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const out = process.argv[2] ?? "media-capture";
const frames = `${out}/frames`;
mkdirSync(frames, { recursive: true });
const APP = "https://main.d1jy52bqj8dt1h.amplifyapp.com";
const DEMO = `${APP}/app/?ws=ws_KFdHFNj0IPUoOs4pQDcMUQ`;
const proxy = process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined;
const browser = await chromium.launch({ proxy });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(e.message));
const pause = (ms) => page.waitForTimeout(ms);

// Frames for the GIF: a screenshot about every 180 ms while `recording` is true.
const stamps = [];
let recording = false;
let n = 0;
async function recorder() {
  while (recording) {
    const t = Date.now();
    await page.screenshot({ path: `${frames}/f${String(n).padStart(4, "0")}.png` }).catch(() => {});
    stamps.push(t);
    n++;
    const wait = 180 - (Date.now() - t);
    if (wait > 0) await pause(wait);
  }
}
async function record(steps) {
  recording = true;
  const running = recorder();
  await steps();
  recording = false;
  await running;
}

await page.goto(DEMO);
await page.getByText(/documents? indexed/).waitFor();
await page.getByText("Answer Review Workflow").first().waitFor({ timeout: 20000 }).catch(() => {});
await pause(800);
await page.getByRole("navigation", { name: "Documents" }).screenshot({ path: `${out}/upload-flow.png` });

const answer = page.getByRole("region", { name: "Answer" });
await record(async () => {
  await pause(1200);
  await page.keyboard.press("Control+k");
  await pause(500);
  await page.keyboard.type("What is the current submission deadline?", { delay: 35 });
  await pause(300);
  await page.keyboard.press("Enter");
  await answer.getByText(/Sources disagree/).first().waitFor({ timeout: 60000 });
  await pause(2500);
});
await page.mouse.move(0, 0);
await page.screenshot({ path: `${out}/hero-dashboard.png` });
await answer.screenshot({ path: `${out}/evidence-chat.png` });

const inspector = page.getByRole("region", { name: "Conflict inspector" });
const timeline = page.getByRole("region", { name: /Timeline/ });
await record(async () => {
  await answer.getByRole("button", { name: /Open evidence 1/ }).first().click();
  await pause(1500);
  await inspector.scrollIntoViewIfNeeded();
  await pause(800);
  await inspector.screenshot({ path: `${out}/conflict-inspector.png` });
  await inspector.getByRole("button", { name: "Why was this flagged?" }).click().catch(() => {});
  await pause(1800);
  await inspector.getByRole("button", { name: "Open the full timeline" }).click();
  await timeline.waitFor();
  await timeline.scrollIntoViewIfNeeded();
  await pause(2500);
});
await timeline.screenshot({ path: `${out}/timeline-view.png` });

await page.evaluate(() => window.scrollTo(0, 0));
const card = page.locator("section[aria-labelledby=workflow-heading]");
await card.scrollIntoViewIfNeeded();
await pause(500);
await card.screenshot({ path: `${out}/workflow-learning-card.png` });
await record(async () => {
  await pause(900);
  await card.getByText("See the events behind it").click();
  await page.getByRole("dialog").waitFor();
  await pause(2800);
});
await page.screenshot({ path: `${out}/workflow-detail-dialog.png` });
await page.keyboard.press("Escape");

// An error card with its request ID: a workspace that doesn't exist (no model call).
await page.goto(`${APP}/app/?ws=ws_videoDrillNotFound0000`);
await page.getByText(/req_/).first().waitFor({ timeout: 30000 });
await pause(600);
await page.screenshot({ path: `${out}/error-request-id.png` });

writeFileSync(`${frames}/stamps.json`, JSON.stringify(stamps));
console.log(JSON.stringify({ frames: n, errors }, null, 2));
await browser.close();
