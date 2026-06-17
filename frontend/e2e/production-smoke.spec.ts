import { expect, request as pwRequest, test } from "@playwright/test";

// Production smoke test for the deployed read-only MVP (docs/PRODUCTION_SMOKE_TEST.md).
// Verifies: read-only landing on /, reports list/detail + Markdown copy, backend health,
// reports API, and that order/paper/automation routes stay 404 and POST /api/reports is 405.
// Read-only only: no secrets, no order APIs, no live trading. Targets public URLs.
const BACKEND_URL =
  process.env.PRODUCTION_BACKEND_URL ?? "https://fx-strategy-lab.onrender.com";

// Render free instances sleep; warm up /health with bounded retries before asserting.
test.beforeAll(async () => {
  const ctx = await pwRequest.newContext();
  let last = "";
  for (let attempt = 0; attempt < 6; attempt++) {
    try {
      const res = await ctx.get(`${BACKEND_URL}/health`, { timeout: 30_000 });
      if (res.ok()) {
        await ctx.dispose();
        return;
      }
      last = `HTTP ${res.status()}`;
    } catch (error) {
      last = error instanceof Error ? error.message : String(error);
    }
    await new Promise((r) => setTimeout(r, 3000));
  }
  await ctx.dispose();
  throw new Error(
    `backend /health not ready after retries (Render free instance may be sleeping / ` +
      `cold start, or backend down): last=${last} url=${BACKEND_URL}`
  );
});

// Deterministic clipboard stub (headless secure-context safe), used by copy checks.
async function stubClipboard(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: async () => {} },
      configurable: true
    });
  });
}

test.describe("production backend smoke", () => {
  test("PSMOKE-01: /health is read-only ok", async ({ request }) => {
    const res = await request.get(`${BACKEND_URL}/health`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
    expect(body.mode).toBe("read-only");
    expect(body.live_trading_environment_enabled).toBe(false);
    expect(body.live_broker_implemented).toBe(false);
  });

  test("PSMOKE-02: /api/reports returns count 4 incl. e2e_normal_run", async ({ request }) => {
    const res = await request.get(`${BACKEND_URL}/api/reports`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.count).toBe(4);
    const ids = body.items.map((i: { run_id: string }) => i.run_id);
    expect(ids).toContain("e2e_normal_run");
  });

  test("PSMOKE-03: detail safety flags are read-only", async ({ request }) => {
    const res = await request.get(`${BACKEND_URL}/api/reports/e2e_normal_run`);
    expect(res.status()).toBe(200);
    const safety = (await res.json()).index.safety;
    expect(safety).toMatchObject({
      real_order: false,
      private_api_used: false,
      api_key_used: false,
      gmo_readonly: true,
      gmo_order_enabled: false,
      no_order_execution: true
    });
  });

  test("PSMOKE-04: dangerous routes absent (404) and reports POST 405", async ({ request }) => {
    expect((await request.get(`${BACKEND_URL}/api/orders`)).status()).toBe(404);
    expect((await request.get(`${BACKEND_URL}/api/paper/sessions`)).status()).toBe(404);
    expect((await request.get(`${BACKEND_URL}/api/automation/status`)).status()).toBe(404);
    expect((await request.post(`${BACKEND_URL}/api/reports`)).status()).toBe(405);
  });
});

test.describe("production frontend smoke", () => {
  test("PSMOKE-05: / is the read-only landing (no dashboard, no fetch error)", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    page.on("pageerror", (e) => errors.push(String(e)));

    await page.goto("/");
    await expect(page.getByTestId("landing-page")).toBeVisible();
    await expect(page.getByTestId("landing-scope")).toContainText("read-only");
    await expect(page.getByTestId("to-reports")).toBeVisible();
    await expect(page.getByTestId("landing-unavailable")).toBeVisible();
    // old dashboard must not leak onto the public top page
    await expect(page.locator(".trading-dashboard")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /バックテスト実行|価格更新|手動停止/ })).toHaveCount(0);
    expect(errors.join("\n")).not.toContain("Failed to fetch");
  });

  test("PSMOKE-06: /reports shows 4 reports and list Markdown copy works", async ({ page }) => {
    await stubClipboard(page);
    await page.goto("/reports");
    await expect(page.getByTestId("reports-page")).toBeVisible();
    await expect(page.getByText("FX Reports")).toBeVisible();
    await expect(page.getByTestId("reports-count")).toContainText("Reports: 4", {
      timeout: 30_000
    });
    await expect(page.locator('[data-run-id="e2e_normal_run"]')).toBeVisible();
    await page.getByTestId("copy-reports-markdown").click();
    await expect(page.getByTestId("copy-reports-markdown-status")).toHaveText(
      "一覧Markdownをコピーしました"
    );
  });

  test("PSMOKE-07: detail shows 7 sections, safe badge, detail Markdown copy", async ({ page }) => {
    await stubClipboard(page);
    await page.goto("/reports/e2e_normal_run");
    await expect(page.getByTestId("report-detail-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Run: e2e_normal_run")).toBeVisible();
    for (const id of [
      "detail-overview",
      "detail-safety",
      "detail-metrics",
      "detail-cost",
      "detail-files",
      "detail-summary-markdown",
      "detail-final-decision"
    ]) {
      await expect(page.getByTestId(id)).toBeVisible();
    }
    await expect(page.getByTestId("safety-badge").first()).toContainText("Read-only確認済み");
    await page.getByTestId("copy-detail-markdown").click();
    await expect(page.getByTestId("copy-detail-markdown-status")).toHaveText(
      "Markdownをコピーしました"
    );
  });
});
