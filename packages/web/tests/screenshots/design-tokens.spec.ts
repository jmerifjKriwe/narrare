/**
 * VRT Screenshot Tests: Design Tokens Page
 *
 * Visual regression tests for the /dev/design-tokens page across light and dark modes,
 * with focused screenshots of each major section (color palette, radii/typography,
 * theme comparison, Tailwind mapping).
 *
 * Font-drift tolerance: text-dominated screenshots (full-page + radii-typo +
 * theme-comparison sections) use `maxDiffPixelRatio: 0.01` to absorb benign 1-2px
 * font-rendering drift between local and CI runners (libpango/libcairo versions
 * differ). This is NOT an "ignore failures" hack — it is a deterministic
 * font-drift absorber calibrated so real layout regressions (which shift far
 * more pixels) still fail. Color-block-dominated sections (#colors, #mapping)
 * do not need it. Complementary to ADR-059 Mock Contract BINDING.
 *
 * @see packages/web/app/(studio)/dev/design-tokens/page.tsx
 */

import { expect, test } from "@playwright/test";

/** Unmocked /api/v1/** requests observed by the catch-all route (reset per test). */
const unmockedApiCalls: string[] = [];

test.describe("Design Tokens Page Screenshots", () => {
  // Pin the timezone so baselines are identical on CI (UTC) and local machines
  // (ADR-059 Mock Contract BINDING — timezoneId is required for every VRT spec).
  test.use({ timezoneId: "UTC" });

  test.beforeEach(async ({ page }) => {
    // Systemic guard: every /api/v1/** request must be explicitly mocked below.
    // Registered FIRST — Playwright tries routes in reverse registration order,
    // so the specific mocks are always checked before this catch-all. Unmocked
    // calls are recorded and asserted empty before the screenshot (ADR-059).
    unmockedApiCalls.length = 0;
    await page.route("**/api/v1/**", async (route) => {
      unmockedApiCalls.push(`${route.request().method()} ${route.request().url()}`);
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unmocked API request in VRT" }),
      });
    });

    // Mock auth — the (studio) layout calls /api/v1/auth/me and redirects on failure
    await page.route("/api/v1/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "user-1",
          email: "test@example.com",
          display_name: "Test User",
          avatar_url: null,
          created_at: "2024-01-01T00:00:00Z",
        }),
      });
    });

    // Mock auth refresh — the auth provider also calls /api/v1/auth/refresh during init
    await page.route("/api/v1/auth/refresh", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "mock-access-token-for-vrt-tests",
          token_type: "bearer",
        }),
      });
    });

    // Suppress the feature tour overlay that blocks pointer events
    // The tour activates on first visit when narrare:featureTourCompleted isn't "true"
    await page.addInitScript(() => {
      localStorage.setItem("narrare:featureTourCompleted", "true");
    });
  });

  test("light mode full page", async ({ page }) => {
    await page.goto("/dev/design-tokens");

    // Wait for the page to fully render
    await expect(page.getByRole("heading", { name: "Design Tokens" })).toHaveText("Design Tokens");

    // Systemic guard: no /api/v1/** request may go unmocked (see beforeEach).
    await expect.poll(() => unmockedApiCalls).toEqual([]);

    // Full-page screenshot in light mode
    // Tolerance for font-rendering drift (libpango/libcairo versions differ
    // local↔CI); calibrated for 1-2px height shift, still catches real layout
    // regressions. See ADR-059.
    await expect(page).toHaveScreenshot("light-mode-full.png", {
      fullPage: true,
      maxDiffPixelRatio: 0.01,
    });
  });

  test("dark mode full page", async ({ page }) => {
    await page.goto("/dev/design-tokens");

    // Wait for the page to fully render
    await expect(page.getByRole("heading", { name: "Design Tokens" })).toHaveText("Design Tokens");

    // Toggle dark mode — button reads "Dark Mode" when previewDark is false
    await page.click('button:has-text("Dark Mode")');

    // Wait for the .dark class to be applied to <html>
    await expect(page.locator("html")).toHaveClass(/dark/);

    // Systemic guard: no /api/v1/** request may go unmocked (see beforeEach).
    await expect.poll(() => unmockedApiCalls).toEqual([]);

    // Full-page screenshot in dark mode
    // Tolerance for font-rendering drift (libpango/libcairo versions differ
    // local↔CI); calibrated for 1-2px height shift, still catches real layout
    // regressions. See ADR-059.
    await expect(page).toHaveScreenshot("dark-mode-full.png", {
      fullPage: true,
      maxDiffPixelRatio: 0.01,
    });
  });

  test("light mode colors section", async ({ page }) => {
    await page.goto("/dev/design-tokens");
    await expect(page.getByRole("heading", { name: "Design Tokens" })).toHaveText("Design Tokens");

    // Systemic guard: no /api/v1/** request may go unmocked (see beforeEach).
    await expect.poll(() => unmockedApiCalls).toEqual([]);

    // Focused screenshot of the Color Palette section
    await expect(page.locator("#colors")).toHaveScreenshot("light-colors-section.png");
  });

  test("light mode radii-typo section", async ({ page }) => {
    await page.goto("/dev/design-tokens");
    await expect(page.getByRole("heading", { name: "Design Tokens" })).toHaveText("Design Tokens");

    // Systemic guard: no /api/v1/** request may go unmocked (see beforeEach).
    await expect.poll(() => unmockedApiCalls).toEqual([]);

    // Focused screenshot of the Radii & Typography section
    // Tolerance for font-rendering drift (libpango/libcairo versions differ
    // local↔CI); calibrated for 1-2px height shift, still catches real layout
    // regressions. See ADR-059.
    await expect(page.locator("#radii-typo")).toHaveScreenshot("light-radii-typo-section.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("light mode theme-comparison section", async ({ page }) => {
    await page.goto("/dev/design-tokens");
    await expect(page.getByRole("heading", { name: "Design Tokens" })).toHaveText("Design Tokens");

    // Systemic guard: no /api/v1/** request may go unmocked (see beforeEach).
    await expect.poll(() => unmockedApiCalls).toEqual([]);

    // Focused screenshot of the Theme Comparison section
    // Tolerance for font-rendering drift (libpango/libcairo versions differ
    // local↔CI); calibrated for 1-2px height shift, still catches real layout
    // regressions. See ADR-059.
    await expect(page.locator("#theme-comparison")).toHaveScreenshot(
      "light-theme-comparison-section.png",
      { maxDiffPixelRatio: 0.01 },
    );
  });

  test("light mode mapping section", async ({ page }) => {
    await page.goto("/dev/design-tokens");
    await expect(page.getByRole("heading", { name: "Design Tokens" })).toHaveText("Design Tokens");

    // Systemic guard: no /api/v1/** request may go unmocked (see beforeEach).
    await expect.poll(() => unmockedApiCalls).toEqual([]);

    // Focused screenshot of the Tailwind Mapping section
    await expect(page.locator("#mapping")).toHaveScreenshot("light-mapping-section.png");
  });
});
