import { defineConfig, devices } from "@playwright/test";

// Production smoke config: targets the already-deployed public URLs (no local webServer).
// Run with `npm run e2e:prod`. Read-only checks only; no secrets, no order APIs.
// Override targets via PRODUCTION_FRONTEND_URL / PRODUCTION_BACKEND_URL.
const FRONTEND_URL =
  process.env.PRODUCTION_FRONTEND_URL ?? "https://fx-strategy-lab.vercel.app";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/production-smoke.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  // Generous per-test timeout to absorb Render free-instance cold start.
  timeout: 90_000,
  use: {
    baseURL: FRONTEND_URL,
    trace: "off",
    screenshot: "off",
    video: "off"
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }]
});
