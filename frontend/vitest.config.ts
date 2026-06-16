import { defineConfig } from "vitest/config";

// Vitest runs the node-env unit tests (lib/**). Playwright specs live under e2e/ and
// are run by Playwright, not Vitest, so they are excluded here.
export default defineConfig({
  test: {
    exclude: ["node_modules/**", "dist/**", ".next/**", "e2e/**"]
  }
});
