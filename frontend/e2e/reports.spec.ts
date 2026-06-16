import { expect, test } from "@playwright/test";

// Read-only E2E for the FX report viewer (docs §16, E2E-01〜08). Runs against the
// generated fixture root (e2e_normal_run / e2e_error_run / e2e_conflict_run /
// e2e_incomplete_run), never the real analysis_exports/.

const CSV_MARKER = "__CSV_BODY_MARKER__";

// Danger words that must not appear as actionable controls (buttons/links/inputs).
const DANGER_WORDS =
  /実注文|決済|建玉取得|Private API|APIキー|secret|\.env|market_order|バックテスト再実行|GMO API取得|OANDA操作|RiskManager操作|DB直接操作/;

test.describe("FX reports read-only E2E", () => {
  test("E2E-01: reports list is shown", async ({ page }) => {
    await page.goto("/reports");
    await expect(page.getByTestId("reports-page")).toBeVisible();
    await expect(page.getByTestId("reports-table")).toBeVisible();
    await expect(page.getByTestId("reports-count")).toBeVisible();
    expect(await page.getByTestId("report-row").count()).toBeGreaterThan(0);
  });

  test("E2E-02: normal run shows SAFE_READ_ONLY badge", async ({ page }) => {
    await page.goto("/reports");
    const row = page.locator('[data-run-id="e2e_normal_run"]');
    await expect(row).toBeVisible();
    const badge = row.getByTestId("safety-badge");
    await expect(badge).toHaveText(/Read-only確認済み/);
    await expect(badge).toHaveAttribute("data-safe", "true");
  });

  test("E2E-03: error run is shown as ERROR (not safe)", async ({ page }) => {
    await page.goto("/reports");
    const row = page.locator('[data-run-id="e2e_error_run"]');
    await expect(row).toBeVisible();
    await expect(row).toHaveAttribute("data-testid", "error-row");
    await expect(row.getByTestId("safety-badge")).not.toHaveText(/Read-only確認済み/);
  });

  test("E2E-04: can navigate to run detail", async ({ page }) => {
    await page.goto("/reports");
    await page
      .locator('[data-run-id="e2e_normal_run"]')
      .getByRole("link", { name: "e2e_normal_run" })
      .click();
    // First navigation to the dynamic route may trigger an on-demand dev compile;
    // wait for the detail page to render before asserting the URL.
    await expect(page.getByTestId("report-detail-page")).toBeVisible({
      timeout: 20_000
    });
    await expect(page).toHaveURL(/\/reports\/e2e_normal_run$/);
  });

  test("E2E-05: detail page shows all seven sections", async ({ page }) => {
    await page.goto("/reports/e2e_normal_run");
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
  });

  test("E2E-06: no dangerous controls on list or detail", async ({ page }) => {
    for (const path of ["/reports", "/reports/e2e_normal_run"]) {
      await page.goto(path);
      await expect(page.getByRole("button", { name: DANGER_WORDS })).toHaveCount(0);
      await expect(page.getByRole("link", { name: DANGER_WORDS })).toHaveCount(0);
      await expect(page.getByRole("textbox", { name: DANGER_WORDS })).toHaveCount(0);
      await expect(page.getByRole("checkbox", { name: DANGER_WORDS })).toHaveCount(0);
    }
  });

  test("E2E-07: CSV metadata shows but CSV body is not expanded", async ({ page }) => {
    await page.goto("/reports/e2e_normal_run");
    await expect(page.getByTestId("detail-files")).toBeVisible();
    await expect(page.getByText("metrics_by_window.csv")).toBeVisible();
    await expect(page.locator("body")).not.toContainText(CSV_MARKER);
  });

  test("E2E-08: conflict/incomplete runs are not treated as safe", async ({ page }) => {
    await page.goto("/reports");
    const conflict = page
      .locator('[data-run-id="e2e_conflict_run"]')
      .getByTestId("safety-badge");
    await expect(conflict).toHaveText(/Safety conflict/);
    await expect(conflict).toHaveAttribute("data-safe", "false");

    const incomplete = page
      .locator('[data-run-id="e2e_incomplete_run"]')
      .getByTestId("safety-badge");
    await expect(incomplete).toHaveText(/Safety incomplete/);
    await expect(incomplete).toHaveAttribute("data-safe", "false");
  });

  test("E2E-09: detail markdown can be copied", async ({ page }) => {
    // Deterministic clipboard stub: avoids headless secure-context/permission flakiness
    // while still exercising button -> fetch -> writeText -> success message.
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText: async () => {} },
        configurable: true
      });
    });
    await page.goto("/reports/e2e_normal_run");
    const button = page.getByTestId("copy-detail-markdown");
    await expect(button).toBeVisible();
    await button.click();
    await expect(page.getByTestId("copy-detail-markdown-status")).toHaveText(
      "Markdownをコピーしました"
    );
  });
});
