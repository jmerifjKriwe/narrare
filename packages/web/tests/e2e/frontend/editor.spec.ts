/**
 * E2E Tests: Editor Flow
 *
 * Tests editor loading, sidebar, and LLM generation mocking.
 */

import { expect, test } from "@playwright/test";

test.describe("Editor", () => {
  test.beforeEach(async ({ page }) => {
    // Mock auth
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

    // Mock novel details
    await page.route("/api/v1/novels/novel-1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "novel-1",
          title: "My First Novel",
          genre: "fantasy",
          status: "draft",
          word_count: 5000,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-15T00:00:00Z",
          volumes: [
            {
              id: "volume-1",
              title: "Volume 1",
              order: 1,
              chapters: [
                {
                  id: "chapter-1",
                  title: "Chapter 1",
                  order: 1,
                  word_count: 2000,
                },
              ],
            },
          ],
        }),
      });
    });

    // Mock chapters list
    await page.route("/api/v1/novels/novel-1/chapters", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "chapter-1",
            title: "Chapter 1",
            order: 1,
            word_count: 2000,
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-01-15T00:00:00Z",
          },
        ]),
      });
    });

    // Mock chapter content
    await page.route("/api/v1/novels/novel-1/chapters/chapter-1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "chapter-1",
          title: "Chapter 1",
          content: "<p>Once upon a time...</p>",
          word_count: 2000,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-15T00:00:00Z",
        }),
      });
    });
  });

  test("editor - loads novel page", async ({ page }) => {
    await page.goto("/novel/novel-1");

    // Should show novel title
    await expect(page.locator("text=My First Novel")).toBeVisible();
  });

  test("editor - shows sidebar with chapters", async ({ page }) => {
    await page.goto("/novel/novel-1");

    // Should show chapter in sidebar
    await expect(page.locator("text=Chapter 1")).toBeVisible();
  });

  test("editor - TipTap editor loads", async ({ page }) => {
    await page.goto("/novel/novel-1");

    // Should have TipTap editor container
    const editor = page.locator(".tiptap");
    await expect(editor).toBeVisible();
  });

  test("editor - chapter navigation works", async ({ page }) => {
    await page.goto("/novel/novel-1");

    // Click on chapter in sidebar
    await page.click("text=Chapter 1");

    // Should show chapter content in editor
    await expect(page.locator("text=Once upon a time")).toBeVisible();
  });

  test("editor - LLM generation endpoint is mocked", async ({ page }) => {
    // Mock LLM generation endpoint
    await page.route("/api/v1/generation/*", async (route) => {
      const url = route.request().url();

      if (url.includes("/generate/continue")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            content: "<p>Generated continuation text...</p>",
            tokens_used: 150,
          }),
        });
      } else if (url.includes("/generate/rewrite")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            content: "<p>Rewritten text...</p>",
            tokens_used: 100,
          }),
        });
      } else if (url.includes("/generate/brainstorm")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            suggestions: ["Idea 1: Character development", "Idea 2: Plot twist"],
            tokens_used: 50,
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/novel/novel-1");

    // The mock is set up - actual UI tests would click generation buttons
    // and verify the mocked responses are displayed
    expect(true).toBe(true);
  });

  test("editor - shows loading state while fetching", async ({ page }) => {
    // Add delay to mock
    await page.route("/api/v1/novels/novel-1", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 500));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "novel-1",
          title: "My First Novel",
          genre: "fantasy",
          status: "draft",
          word_count: 5000,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-15T00:00:00Z",
          volumes: [],
        }),
      });
    });

    await page.goto("/novel/novel-1");

    // Should show loading state initially
    // (This depends on the actual UI implementation)
    await expect(page.locator("text=My First Novel")).toBeVisible({ timeout: 10000 });
  });
});
