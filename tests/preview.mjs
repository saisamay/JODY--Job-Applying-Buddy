import assert from "node:assert/strict";
import { chromium, expect } from "@playwright/test";

// Run against a deployed preview or an explicitly loopback-only rehearsal.
const web = new URL(process.env.WEB_BASE_URL);
const api = new URL(process.env.API_BASE_URL);
const key = process.env.JODY_OWNER_KEY;
assert.ok(key, "Configure the preview owner's access key");
for (const url of [web, api]) {
  assert.ok(!url.username && !url.password && url.pathname === "/");
  assert.ok(url.protocol === "https:" || url.hostname === "127.0.0.1");
}
const get = (path, options = {}) =>
  fetch(new URL(path, api), {
    ...options,
    redirect: "error",
    signal: AbortSignal.timeout(100_000),
  });
assert.equal((await (await get("/health/live")).json()).status, "live");
assert.deepEqual(await (await get("/health/ready")).json(), {
  status: "ready",
  postgres: true,
  redis: true,
});
assert.equal((await get("/api/v1/workspace")).status, 401);
const preflight = await get("/api/v1/session", {
  method: "OPTIONS",
  headers: {
    Origin: web.origin,
    "Access-Control-Request-Method": "POST",
  },
});
assert.equal(preflight.headers.get("access-control-allow-origin"), null);

const browser = await chromium.launch({
  executablePath: process.env.CHROME_BIN || undefined,
});
try {
  const context = await browser.newContext({
    baseURL: web.origin,
    storageState: process.env.JODY_BROWSER_STATE || undefined,
  });
  if (process.env.VERCEL_OIDC_TOKEN) {
    assert.equal(web.protocol, "https:");
    await context.route(
      (url) => url.origin === web.origin,
      (route) =>
        route.continue({
          headers: {
            ...route.request().headers(),
            "x-vercel-trusted-oidc-idp-token": process.env.VERCEL_OIDC_TOKEN,
          },
        }),
    );
  }
  const page = await context.newPage();
  await page.goto("/workspace");
  await expect(page).toHaveURL(/\/signin$/);
  await page.getByLabel("Owner access key").fill(key);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Workspace overview." }),
  ).toBeVisible({ timeout: 90000 });
  const session = (await context.cookies(web.origin)).find(
    (c) => c.name === "jody_session",
  );
  assert.ok(
    session?.httpOnly && session.secure && session.sameSite === "Strict",
  );
  const headers = { Authorization: `Bearer ${session.value}` };
  assert.deepEqual(
    await (await get("/api/v1/system/kill-switch", { headers })).json(),
    { paused: true, locked: true },
  );
  assert.equal((await get("/api/v1/workspace", { headers })).status, 200);
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const name of ["Job discovery", "Integrations", "Overview"]) {
      const mobile = width === 390;
      if (mobile)
        await page.getByRole("button", { name: "Workspace menu" }).click();
      await page
        .getByRole("navigation", {
          name: mobile ? "Mobile workspace navigation" : "Workspace navigation",
          exact: true,
        })
        .getByRole("link", { name, exact: true })
        .click();
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(
        (name === "Overview" ? "Workspace overview" : name) + ".",
      );
      if (name === "Integrations")
        await expect(
          page.getByText(
            "External integrations are disabled for this private preview.",
          ),
        ).toBeVisible();
      assert.ok(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      );
    }
  }
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByLabel("Owner access key")).toBeVisible();
  assert.equal((await get("/api/v1/workspace", { headers })).status, 401);
  console.log(
    "Preview health, database, CORS, secure session, automation lock, mobile and desktop navigation, and sign-out passed.",
  );
} finally {
  await browser.close();
}
