/**
 * VRT Screenshot Tests: Design Tokens Page
 *
 * Visual regression tests for the /dev/design-tokens page across light and dark modes,
 * with focused screenshots of each major section (color palette, radii/typography,
 * theme comparison, Tailwind mapping).
 *
 * @see packages/web/app/(studio)/dev/design-tokens/page.tsx
 */

import { expect, test } from "@playwright/test";

test.describe("Design Tokens Page Screenshots", () => {
  test.beforeEach(async ({ page }) => {
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

    // Full-page screenshot in light mode
    await expect(page).toHaveScreenshot("light-mode-full.png", { fullPage: true });
  });

  test("dark mode full page", async ({ page }) => {
    await page.goto("/dev/design-tokens");

    // Wait for the page to fully render
    await expect(page.getByRole("heading", { name: "Design Tokens" })).toHaveText("Design Tokens");

    // Toggle dark mode — button reads "Dark Mode" when previewDark is false
    await page.click('button:has-text("Dark Mode")');

    // Wait for the .dark class to be applied to <html>
    await expect(page.locator("html")).toHaveClass(/dark/);

    // Full-page screenshot in dark mode
    await expect(page).toHaveScreenshot("dark-mode-full.png", { fullPage: true });
  });

  test("light mode colors section", async ({ page }) => {
    await page.goto("/dev/design-tokens");
    await expect(page.getByRole("heading", { name: "Design Tokens" })).toHaveText("Design Tokens");

    // Focused screenshot of the Color Palette section
    await expect(page.locator("#colors")).toHaveScreenshot("light-colors-section.png");
  });

  test("light mode radii-typo section", async ({ page }) => {
    await page.goto("/dev/design-tokens");
    await expect(page.getByRole("heading", { name: "Design Tokens" })).toHaveText("Design Tokens");

    // Focused screenshot of the Radii & Typography section
    await expect(page.locator("#radii-typo")).toHaveScreenshot("light-radii-typo-section.png");
  });

  test("light mode theme-comparison section", async ({ page }) => {
    await page.goto("/dev/design-tokens");
    await expect(page.getByRole("heading", { name: "Design Tokens" })).toHaveText("Design Tokens");

    // Focused screenshot of the Theme Comparison section
    await expect(page.locator("#theme-comparison")).toHaveScreenshot(
      "light-theme-comparison-section.png",
    );
  });

  test("light mode mapping section", async ({ page }) => {
    await page.goto("/dev/design-tokens");
    await expect(page.getByRole("heading", { name: "Design Tokens" })).toHaveText("Design Tokens");

    // Focused screenshot of the Tailwind Mapping section
    await expect(page.locator("#mapping")).toHaveScreenshot("light-mapping-section.png");
  });
});
