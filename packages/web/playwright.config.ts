import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E Test Configuration
 *
 * Uses existing browser from cache (chromium-1217) to avoid download issues.
 */
export default defineConfig({
  // Test directory
  testDir: "./tests/e2e",

  // Fully parallelize within files
  fullyParallel: true,

  // Fail if no tests found
  forbidOnly: !!process.env.CI,

  // Retry on CI
  retries: process.env.CI ? 2 : 0,

  // Workers
  workers: process.env.CI ? 1 : undefined,

  // Reporter
  reporter: [["html", { outputFolder: "playwright-report" }], ["list"]],

  // Shared settings
  use: {
    // Base URL for all tests
    baseURL: process.env.BASE_URL || "http://localhost:3000",

    // Collect traces on failure
    trace: "on-first-retry",

    // Collect screenshots on failure
    screenshot: "only-on-failure",

    // Video on failure
    video: "retain-on-failure",
  },

  // Projects
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Use cached browser
        channel: "chromium",
      },
    },
  ],

  // Web server - starts automatically for tests
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 120000,
  },
});
