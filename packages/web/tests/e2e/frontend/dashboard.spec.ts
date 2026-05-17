/**
 * E2E Tests: Dashboard Flow
 *
 * Tests dashboard novel list, creation, and deletion with mocked API responses.
 */

import { expect, test } from "@playwright/test";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    // Mock auth - user is logged in
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

    // Mock novels list
    await page.route("/api/v1/novels", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "novel-1",
            title: "My First Novel",
            genre: "fantasy",
            status: "draft",
            word_count: 5000,
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-01-15T00:00:00Z",
          },
          {
            id: "novel-2",
            title: "Second Novel",
            genre: "scifi",
            status: "published",
            word_count: 25000,
            created_at: "2024-02-01T00:00:00Z",
            updated_at: "2024-02-20T00:00:00Z",
          },
        ]),
      });
    });
  });

  test("dashboard - displays user greeting", async ({ page }) => {
    await page.goto("/");

    // Should show user name
    await expect(page.locator("text=Test User")).toBeVisible();
  });

  test("dashboard - displays novel list", async ({ page }) => {
    await page.goto("/");

    // Should show novels
    await expect(page.locator("text=My First Novel")).toBeVisible();
    await expect(page.locator("text=Second Novel")).toBeVisible();
  });

  test("dashboard - displays novel metadata", async ({ page }) => {
    await page.goto("/");

    // Should show genre and status
    await expect(page.locator("text=fantasy")).toBeVisible();
    await expect(page.locator("text=draft")).toBeVisible();
    await expect(page.locator("text=scifi")).toBeVisible();
    await expect(page.locator("text=published")).toBeVisible();
  });

  test("dashboard - new novel button navigates to wizard", async ({ page }) => {
    await page.goto("/");

    // Click new novel button
    await page.click('button:has-text("newNovel")');

    // Should navigate to wizard
    await expect(page).toHaveURL("/wizard");
  });

  test("dashboard - clicking novel navigates to editor", async ({ page }) => {
    await page.goto("/");

    // Click on first novel
    await page.click("text=My First Novel");

    // Should navigate to novel page
    await expect(page).toHaveURL("/novel/novel-1");
  });

  test("dashboard - logout button exists", async ({ page }) => {
    await page.goto("/");

    // Should have logout button
    const logoutButton = page.locator('button:has-text("logout")');
    await expect(logoutButton).toBeVisible();
  });

  test("dashboard - empty state when no novels", async ({ page }) => {
    // Override novels to return empty array
    await page.route("/api/v1/novels", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto("/");

    // Should show empty state message
    await expect(page.locator("text=novelsEmpty")).toBeVisible();
  });
});
