import test from "node:test";
import { chromium, expect } from "@playwright/test";

test("owner can sign in, save a manual job, reload, retry and sign out", async () => {
  const key = process.env.JODY_OWNER_KEY;
  if (!key) throw new Error("Set JODY_OWNER_KEY for the local smoke test");
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_BIN,
  });
  try {
    const page = await browser.newPage();
    await page.goto(process.env.WEB_BASE_URL || "http://127.0.0.1:3000");
    await expect(page.getByText("Services ready")).toBeVisible();
    await page.getByLabel("Owner access key").fill(key);
    await page.getByRole("button", { name: "Open workspace" }).click();
    await expect(page.getByText("Background tasks paused")).toBeVisible();
    await page.getByRole("button", { name: "Resume tasks" }).click();
    await expect(page.getByText("Background tasks active")).toBeVisible();
    await page.getByRole("button", { name: "Pause all tasks" }).click();
    await expect(page.getByText("Background tasks paused")).toBeVisible();
    const fixture = "Synthetic JODY foundation smoke vacancy";
    for (let attempt = 0; attempt < 2; attempt++) {
      await page.getByLabel("Job description").fill(fixture);
      await page
        .getByLabel("Source URL")
        .fill("https://example.org/jobs/foundation-smoke");
      await page.getByRole("button", { name: "Save job" }).click();
      await expect(page.getByText("Job saved.", { exact: true })).toBeVisible();
      await page.reload();
      await expect(page.getByText(fixture, { exact: true })).toHaveCount(1);
    }
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page.getByLabel("Owner access key")).toBeVisible();
  } finally {
    await browser.close();
  }
});
