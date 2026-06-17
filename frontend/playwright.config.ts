import { defineConfig, devices } from "@playwright/test";

// Minimal read-only E2E setup (docs §16 / §16-16). Chromium only, no CI wiring.
// Two local servers are started: the FastAPI backend (pointed at a generated fixture
// root via ANALYSIS_EXPORTS_ROOT, NOT the real analysis_exports/) and the Next.js dev
// server (pointed at the backend via NEXT_PUBLIC_API_BASE_URL). The backend command
// regenerates the fixtures first so the run set is deterministic.

const FIXTURE_ROOT = "../frontend/e2e/fixtures/analysis_exports";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  // The production smoke spec targets already-deployed public URLs and has its own
  // config (playwright.prod.config.ts / `npm run e2e:prod`); keep it out of local E2E.
  testIgnore: "**/production-smoke.spec.ts",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "off",
    screenshot: "off",
    video: "off"
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } }
  ],
  webServer: [
    {
      // Generate fixtures, then serve the backend against that fixture root.
      command:
        `cd ../backend && .venv/bin/python -m scripts.create_e2e_report_fixtures ` +
        `--output-root ${FIXTURE_ROOT} && ` +
        `ANALYSIS_EXPORTS_ROOT=${FIXTURE_ROOT} ` +
        `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      env: { NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000" },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000
    }
  ]
});
