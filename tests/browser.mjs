import test from "node:test";
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const base = process.env.WEB_BASE_URL || "http://127.0.0.1:3000";
const widths = [360, 390, 768, 1024, 1440];
const views = [
  ["Job discovery", "discovery"],
  ["Applications", "applications"],
  ["Approval inbox", "approvals"],
  ["Resume manager", "resumes"],
  ["Projects & portfolio", "projects"],
  ["Match analysis", "analysis"],
  ["Recruiter outreach", "outreach"],
  ["Gmail updates", "gmail"],
  ["Integrations", "integrations"],
  ["Settings", "settings"],
  ["Audit history", "audit"],
  ["Overview", "overview"],
];

async function fits(page) {
  const clipped = await page.evaluate(() => {
    const w = document.documentElement.clientWidth;
    return [...document.querySelectorAll("main *, header *, nav *, .sidebar *")]
      .filter((el) => {
        const b = el.getBoundingClientRect();
        return (
          b.width > 1 &&
          b.height > 1 &&
          (b.right > w + 1 || b.left < -1) &&
          !el.classList.contains("sr-only")
        );
      })
      .slice(0, 4)
      .map((e) => e.tagName + "." + e.className);
  });
  assert.deepEqual(clipped, [], `Visible overflow at ${page.url()}`);
  assert.ok(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth + 1,
    ),
  );
}
async function accessibility(page) {
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  assert.deepEqual(
    scan.violations.map((v) => [v.id, v.nodes.map((n) => n.target)]),
    [],
  );
}
async function selectView(page, label) {
  if (await page.getByRole("button", { name: "Workspace menu" }).isVisible()) {
    await page.getByRole("button", { name: "Workspace menu" }).click();
    await page
      .getByRole("navigation", { name: "Mobile workspace navigation" })
      .getByRole("link", { name: label, exact: true })
      .click();
  } else {
    await page
      .getByRole("navigation", { name: "Workspace navigation", exact: true })
      .getByRole("link", { name: label, exact: true })
      .click();
  }
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    (label === "Overview" ? "Workspace overview" : label) + ".",
  );
}
async function capture(page, name, width) {
  // Enable private captures only on an explicitly selected synthetic QA stack.
  const dest = process.env.JODY_UI_CAPTURE_DIR;
  if (!dest || process.env.JODY_SYNTHETIC_WORKSPACE !== "1") return;
  await mkdir(dest, { recursive: true });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: path.join(dest, `${name}-${width}.png`),
    fullPage: true,
    animations: "disabled",
  });
}
function fixturePdf() {
  const parts = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 500] /Resources << >> >>",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  for (const [i, part] of parts.entries()) {
    offsets.push(pdf.length);
    pdf += `${i + 1} 0 obj\n${part}\nendobj\n`;
  }
  const xref = pdf.length;
  pdf +=
    "xref\n0 4\n0000000000 65535 f \n" +
    offsets
      .slice(1)
      .map((o) => String(o).padStart(10, "0") + " 00000 n \n")
      .join("") +
    `trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf);
}

test(
  "public exploration and private workspace across five viewports",
  { timeout: 300000 },
  async () => {
    const key = process.env.JODY_OWNER_KEY;
    assert.ok(key, "Set the private local owner key.");
    const browser = await chromium.launch({
      executablePath: process.env.CHROME_BIN,
    });
    const ctx = await browser.newContext({
      baseURL: base,
      reducedMotion: "reduce",
    });
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (err) => errors.push(err.message));
    try {
      for (const width of widths) {
        await page.setViewportSize({ width, height: width > 800 ? 960 : 844 });
        await page.goto("/");
        await expect(page.getByRole("heading", { level: 1 })).toContainText(
          "Your Job Hunt.",
        );
        await fits(page);
        await capture(page, "landing", width);
        if (width === 360 || width === 1440) await accessibility(page);
        if (width < 851) {
          await page.getByRole("button", { name: "Navigation menu" }).click();
          await page
            .getByRole("navigation", { name: "Mobile navigation" })
            .getByRole("link", { name: "Features", exact: true })
            .click();
          await expect(page).toHaveURL(/#features$/);
        }
        await page
          .getByLabel("Search sample roles")
          .fill("work from home Python");
        await page.getByRole("button", { name: "Explore roles" }).click();
        await expect(page.locator(".example-row")).toHaveCount(1);
        await page.locator(".example-row").click();
        await expect(page.locator(".example-detail")).toContainText("APIs");
        await page.getByLabel("Search sample roles").fill("x".repeat(120));
        await page.getByRole("button", { name: "Explore roles" }).click();
        await expect(page.getByText(/No sample roles match/)).toBeVisible();
        await page
          .getByRole("button", { name: "Applications", exact: true })
          .click();
        await expect(
          page.getByRole("heading", { name: "Application board" }),
        ).toBeVisible();
      }
      await page.goto("/workspace");
      await expect(page).toHaveURL(/\/signin$/);
      await expect(page.getByText("Services ready")).toBeVisible();
      await page.getByLabel("Owner access key").fill("incorrect synthetic key");
      await page.getByRole("button", { name: "Open workspace" }).click();
      await expect(page.getByRole("status")).toContainText(/invalid/i);
      await page.getByLabel("Owner access key").fill(key);
      await page.getByRole("button", { name: "Open workspace" }).click();
      await expect(page).toHaveURL(/\/workspace$/);
      for (const width of widths) {
        await page.setViewportSize({ width, height: width > 800 ? 960 : 844 });
        await expect(
          page.getByRole("heading", { name: "Workspace overview." }),
        ).toBeVisible();
        await fits(page);
        await capture(page, "dashboard", width);
        if (width === 360 || width === 1440) await accessibility(page);
        for (const [label] of views) {
          await selectView(page, label);
          await fits(page);
          if (width === 390) await accessibility(page);
        }
      }
      await selectView(page, "Integrations");
      await page
        .getByRole("combobox", { name: "Provider" })
        .selectOption("groq");
      await page
        .getByLabel("Access credential")
        .fill("synthetic-browser-fixture");
      await page
        .getByRole("button", { name: "Store credential", exact: true })
        .click();
      const groqCard = page
        .locator(".connection")
        .filter({ has: page.getByText("Groq", { exact: true }) });
      await expect(groqCard).toContainText("Authorization required");
      await page
        .getByLabel("Remove this credential from my JODY vault")
        .check();
      await page
        .getByRole("button", { name: "Remove stored credential" })
        .click();
      await expect(groqCard).toContainText("Disconnected");
      await selectView(page, "Overview");
      await expect(page.getByText("Background tasks paused")).toBeVisible();
      await page.getByRole("button", { name: "Resume tasks" }).click();
      await expect(page.getByText("Background tasks active")).toBeVisible();
      await page.getByRole("button", { name: "Pause all tasks" }).click();
      await expect(page.getByText("Background tasks paused")).toBeVisible();
      await selectView(page, "Job discovery");
      const fixture = "Synthetic JODY foundation smoke vacancy";
      for (let i = 0; i < 2; i++) {
        await page.getByLabel("Job description").fill(fixture);
        await page
          .getByLabel("Source URL")
          .fill("https://example.org/jobs/foundation-smoke");
        await page.getByRole("button", { name: "Save job" }).click();
        await expect(
          page.getByText("Job saved.", { exact: true }),
        ).toBeVisible();
        await page.reload();
        await expect(
          page.locator("summary").filter({ hasText: fixture }),
        ).toHaveCount(1);
      }
      await page.getByLabel("Filter saved jobs").fill("this does not exist");
      await expect(
        page.getByRole("heading", { name: "No matching roles" }),
      ).toBeVisible();
      await page.getByLabel("Filter saved jobs").fill(fixture);
      await page.locator("summary").filter({ hasText: fixture }).click();
      await expect(page.getByText("Trust not assessed")).toBeVisible();
      await selectView(page, "Match analysis");
      await page
        .getByRole("button", { name: "Compare qualifications" })
        .click();
      await expect(
        page.getByText(/Internal qualification estimate/),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "PDF scoring unavailable" }),
      ).toBeDisabled();
      await selectView(page, "Resume manager");
      const name = "Browser fixture " + Date.now();
      const bytes = fixturePdf();
      await page.getByLabel("Resume label").fill(name);
      await page.getByLabel("PDF file").setInputFiles({
        name: "fixture.pdf",
        mimeType: "application/pdf",
        buffer: bytes,
      });
      await page.getByRole("button", { name: "Upload PDF" }).click();
      await expect(
        page.getByText("Resume uploaded.", { exact: true }),
      ).toBeVisible();
      await page.getByRole("button", { name: new RegExp(name) }).click();
      const pdf = await page
        .getByTitle("Private resume PDF preview")
        .getAttribute("src");
      const response = await ctx.request.get(pdf);
      assert.equal(response.status(), 200);
      assert.deepEqual(await response.body(), bytes);
      await page.getByText("Edit resume details", { exact: true }).click();
      await page.getByLabel("Display label").fill(name + " revised");
      await page.getByRole("button", { name: "Save resume details" }).click();
      await expect(
        page.getByText("Resume details saved.", { exact: true }),
      ).toBeVisible();
      await page.getByText("Remove this upload", { exact: true }).click();
      await page.getByLabel("Remove this PDF from my resume library").check();
      await page.getByRole("button", { name: "Remove selected PDF" }).click();
      await expect(
        page.getByRole("button", { name: new RegExp(name) }),
      ).toHaveCount(0);
      assert.equal((await ctx.request.get(pdf)).status(), 404);
      await selectView(page, "Settings");
      const block = page.locator("details").filter({
        has: page.getByText("Manage blocklist", { exact: true }),
      });
      await block.locator("summary").click();
      const domain = `browser-${crypto.randomUUID()}.invalid`;
      await block.getByLabel("Value", { exact: true }).fill(domain);
      await block.getByLabel("Reason").fill("Synthetic test");
      await block.getByRole("button", { name: "Apply policy" }).click();
      await expect(block.getByRole("status")).toHaveText("Policy saved.");
      await expect(page.getByText(domain, { exact: true })).toBeVisible();
      await block.locator("select[name=operation]").selectOption("remove");
      await block.getByLabel("Value", { exact: true }).fill(domain);
      await block.getByLabel("Reason").fill("Test complete");
      await block.getByRole("button", { name: "Apply policy" }).click();
      await expect(block.getByRole("status")).toHaveText("Policy removed.");
      await expect(page.getByText(domain, { exact: true })).toHaveCount(0);
      await page.getByRole("button", { name: "Sign out" }).click();
      await expect(page.getByLabel("Owner access key")).toBeVisible();
      assert.equal((await ctx.request.get(pdf)).status(), 401);
      assert.deepEqual(errors, []);
    } finally {
      await browser.close();
    }
  },
);

test("Gmail source and synchronization presentation", async () => {
  const { gmailSource, runState } =
    await import("../apps/web/lib/gmail-display.ts");
  assert.equal(gmailSource("linkedin.com"), "Gmail · LinkedIn Job Alerts");
  assert.equal(
    runState("Synchronizing", "pending", false, false, false),
    "Waiting for continuation",
  );
  assert.equal(
    runState("Synchronizing", "pending", false, true, true),
    "Finalizing",
  );
  assert.equal(
    runState("Synchronizing", "pending", true, false, false),
    "Paused by owner",
  );
  assert.equal(
    runState("Authorization expired", "failed", false, false, false),
    "Authorization expired",
  );
});
