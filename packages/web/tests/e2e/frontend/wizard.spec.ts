/**
 * E2E Tests: Wizard Flow
 *
 * Tests the complete new novel creation wizard with mocked API responses.
 */

import { expect, test } from "@playwright/test";

test.describe("Wizard Flow", () => {
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

    // Mock validation endpoints for each step
    await page.route("/api/v1/setup/validate/step-1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ valid: true }),
      });
    });

    await page.route("/api/v1/setup/validate/step-2", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ valid: true }),
      });
    });

    await page.route("/api/v1/setup/validate/step-3", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ valid: true, starter: "blank", demo_info: null }),
      });
    });

    await page.route("/api/v1/setup/validate/step-4", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ valid: true }),
      });
    });

    // Mock provider models
    await page.route("/api/v1/setup/providers/:provider/models", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { id: "gpt-4", name: "GPT-4" },
          { id: "claude-3-opus-20240229", name: "Claude 3 Opus" },
        ]),
      });
    });

    // Mock setup complete
    await page.route("/api/v1/setup/complete", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          novel_id: "new-novel-id",
          redirect_to: "/novel/new-novel-id",
          message: "Setup complete",
        }),
      });
    });

    // Mock novel fetch after redirect (for verification)
    await page.route("/api/v1/novels/:novelId", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "new-novel-id",
          title: "Test Novel",
          author: "Test Author",
          genre: "fantasy",
          language: "en",
          is_demo: false,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        }),
      });
    });
  });

  test("wizard - step 1: project basics", async ({ page }) => {
    await page.goto("/wizard");

    // Should be on step 1
    await expect(page.locator('text="Project Basics"')).toBeVisible();
    await expect(page.locator('text="currentStep"')).toHaveText(/1/);

    // Fill form
    await page.fill('input[name="project_name"]', "My Novel Project");
    await page.fill('input[name="language"]', "en");
    await page.fill('input[name="autosave_interval"]', "60");

    // Click next
    await page.click('button:has-text("Next")');

    // Should advance to step 2
    await expect(page.locator('text="Story Details"')).toBeVisible();
    await expect(page.locator('text="currentStep"')).toHaveText(/2/);
  });

  test("wizard - step 2: story details", async ({ page }) => {
    await page.goto("/wizard");

    // Pre-fill step 1 via API? Actually we need to go through step 1 first.
    // Instead, we can directly navigate to step 2 by setting state? Not possible.
    // Better: fill step 1 and click next, then fill step 2.
    // We'll do that in this test.

    // Fill step 1
    await page.fill('input[name="project_name"]', "My Novel Project");
    await page.fill('input[name="language"]', "en");
    await page.fill('input[name="autosave_interval"]', "30");
    await page.click('button:has-text("Next")');

    // Now on step 2
    await expect(page.locator('text="Story Details"')).toBeVisible();

    // Fill form
    await page.fill('input[name="title"]', "Epic Fantasy Tale");
    await page.fill('input[name="author"]', "Jane Doe");
    await page.fill('input[name="genre"]', "fantasy");
    await page.fill('input[name="logline"]', "A young wizard discovers their destiny.");

    // Select story structure (assuming radio or select)
    await page.selectOption('select[name="story_structure"]', "three_act");
    // Select tone
    await page.selectOption('select[name="tone"]', "dramatic");

    // Click next
    await page.click('button:has-text("Next")');

    // Should advance to step 3
    await expect(page.locator('text="Starter Content"')).toBeVisible();
    await expect(page.locator('text="currentStep"')).toHaveText(/3/);
  });

  test("wizard - step 3: starter content", async ({ page }) => {
    // Go through steps 1 and 2 quickly
    await page.goto("/wizard");
    await page.fill('input[name="project_name"]', "Project");
    await page.fill('input[name="language"]', "en");
    await page.fill('input[name="autosave_interval"]', "30");
    await page.click('button:has-text("Next")');

    await page.fill('input[name="title"]', "Title");
    await page.fill('input[name="author"]', "Author");
    await page.fill('input[name="genre"]', "fantasy");
    await page.fill('input[name="logline"]', "Logline");
    await page.selectOption('select[name="story_structure"]', "three_act");
    await page.selectOption('select[name="tone"]', "dramatic");
    await page.click('button:has-text("Next")');

    // Now on step 3
    await expect(page.locator('text="Starter Content"')).toBeVisible();

    // Choose blank starter
    await page.click('label:has-text("Blank")'); // Assuming radio label
    // Or if it's a button group
    // await page.click('text="Blank"');

    // Click next
    await page.click('button:has-text("Next")');

    // Should advance to step 4
    await expect(page.locator('text="AI Settings"')).toBeVisible();
    await expect(page.locator('text="currentStep"')).toHaveText(/4/);
  });

  test("wizard - step 4: AI settings", async ({ page }) => {
    // Go through steps 1-3
    await page.goto("/wizard");
    await page.fill('input[name="project_name"]', "Project");
    await page.fill('input[name="language"]', "en");
    await page.fill('input[name="autosave_interval"]', "30");
    await page.click('button:has-text("Next")');

    await page.fill('input[name="title"]', "Title");
    await page.fill('input[name="author"]', "Author");
    await page.fill('input[name="genre"]', "fantasy");
    await page.fill('input[name="logline"]', "Logline");
    await page.selectOption('select[name="story_structure"]', "three_act");
    await page.selectOption('select[name="tone"]', "dramatic");
    await page.click('button:has-text("Next")');

    await page.click('label:has-text("Blank")');
    await page.click('button:has-text("Next")');

    // Now on step 4
    await expect(page.locator('text="AI Settings"')).toBeVisible();

    // Fill form
    await page.selectOption('select[name="provider"]', "anthropic");
    await page.fill('input[name="api_key"]', "test-api-key");
    await page.fill('input[name="model"]', "claude-3-opus-20240229");
    await page.fill('input[name="ollama_url"]', "http://localhost:11434");
    await page.fill('input[name="zai_endpoint"]', "general");

    // Click complete
    await page.click('button:has-text("Complete")');

    // Should redirect to novel page
    await expect(page).toHaveURL("/novel/new-novel-id");
  });

  test("wizard - validation errors on step 1", async ({ page }) => {
    await page.goto("/wizard");

    // Submit empty form
    await page.click('button:has-text("Next")');

    // Should show errors (assuming validation)
    // Depending on implementation, might show inline errors
    // We'll just check that we don't advance
    await expect(page.locator('text="Project Basics"')).toBeVisible();
    await expect(page.locator('text="currentStep"')).toHaveText(/1/);
  });
});
