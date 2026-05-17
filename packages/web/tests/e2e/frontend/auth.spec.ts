/**
 * E2E Tests: Authentication Flow
 *
 * Tests login and registration flows with mocked API responses.
 */

import { expect, test } from "@playwright/test";

test.describe("Authentication", () => {
  test.beforeEach(async ({ page }) => {
    // Mock auth endpoints
    await page.route("/api/v1/auth/login", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "mock-access-token",
          token_type: "bearer",
        }),
      });
    });

    await page.route("/api/v1/auth/register", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "mock-access-token",
          token_type: "bearer",
        }),
      });
    });

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
  });

  test("login flow - successful login redirects to dashboard", async ({ page }) => {
    await page.goto("/login");

    // Fill login form
    await page.fill("#login-email", "test@example.com");
    await page.fill("#login-password", "password123");

    // Submit form
    await page.click('button[type="submit"]');

    // Should redirect to dashboard
    await expect(page).toHaveURL("/");
  });

  test("login flow - shows error on invalid credentials", async ({ page }) => {
    // Override login to return 401
    await page.route("/api/v1/auth/login", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid credentials" }),
      });
    });

    await page.goto("/login");

    await page.fill("#login-email", "test@example.com");
    await page.fill("#login-password", "wrongpassword");

    await page.click('button[type="submit"]');

    // Should show error message
    await expect(page.locator("text=Invalid credentials")).toBeVisible();
  });

  test("register flow - successful registration redirects to dashboard", async ({ page }) => {
    await page.goto("/register");

    // Fill registration form
    await page.fill("#register-email", "newuser@example.com");
    await page.fill("#register-password", "password123");
    await page.fill("#register-displayName", "New User");

    await page.click('button[type="submit"]');

    // Should redirect to dashboard
    await expect(page).toHaveURL("/");
  });

  test("login page - has link to register page", async ({ page }) => {
    await page.goto("/login");

    // Check register link exists
    const registerLink = page.locator('a:has-text("signUp")');
    await expect(registerLink).toBeVisible();
    await expect(registerLink).toHaveAttribute("href", "/register");
  });

  test("register page - has link to login page", async ({ page }) => {
    await page.goto("/register");

    // Check login link exists
    const loginLink = page.locator('a:has-text("noAccount")');
    await expect(loginLink).toBeVisible();
  });
});
