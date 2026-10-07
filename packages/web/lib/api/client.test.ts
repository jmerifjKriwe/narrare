import { beforeEach, describe, expect, it, vi } from "vitest";

// @vitest-environment jsdom

import { HttpResponse, http } from "msw";
import { server } from "@/mocks/server";
import {
  authApi,
  chaptersApi,
  clearAccessToken,
  getAccessToken,
  logoutApi,
  novelsApi,
  restoreSession,
  setAccessToken,
} from "./client";
import { ApiError, fetchApi, isBudgetExceededError } from "./core";

describe("API Client", () => {
  beforeEach(() => {
    clearAccessToken();
  });

  describe("token management", () => {
    it("should start with no access token", () => {
      expect(getAccessToken()).toBeNull();
    });

    it("should store an access token after setAccessToken", () => {
      setAccessToken("my-test-token");

      expect(getAccessToken()).toBe("my-test-token");
    });

    it("should clear the access token after clearAccessToken", () => {
      setAccessToken("my-test-token");
      clearAccessToken();

      expect(getAccessToken()).toBeNull();
    });
  });

  describe("authApi", () => {
    it("should login and return tokens", async () => {
      const result = await authApi.login("test@example.com", "password123");

      expect(result).toEqual({
        access_token: "test-access-token",
        refresh_token: "test-refresh-token",
        token_type: "bearer",
        expires_in: 3600,
      });
    });

    it("should register and return tokens", async () => {
      const result = await authApi.register("new@example.com", "pass123", "Test User");

      expect(result).toHaveProperty("access_token");
      expect(result).toHaveProperty("refresh_token");
      expect(result.token_type).toBe("bearer");
    });

    it("should return current user from /auth/me", async () => {
      setAccessToken("test-access-token");
      const user = await authApi.me();

      expect(user).toHaveProperty("id");
      expect(user).toHaveProperty("email");
      expect(user.email).toBe("test@example.com");
    });

    it("should auto-refresh and succeed when no token exists but refresh cookie is valid", async () => {
      // No access token set — fetchApi will get 401, then refresh via cookie and retry
      clearAccessToken();

      const user = await authApi.me();

      expect(user).toHaveProperty("id");
      expect(user.email).toBe("test@example.com");
      // After auto-refresh, the refreshed token should be stored
      expect(getAccessToken()).toBe("refreshed-access-token");
    });
  });

  describe("novelsApi", () => {
    beforeEach(() => {
      setAccessToken("test-access-token");
    });

    it("should list novels", async () => {
      const novels = await novelsApi.list();

      expect(Array.isArray(novels)).toBe(true);
      expect(novels.length).toBeGreaterThan(0);
      expect(novels[0]).toHaveProperty("id");
      expect(novels[0]).toHaveProperty("title");
    });

    it("should get a single novel", async () => {
      const novel = await novelsApi.get("novel-1");

      expect(novel.id).toBe("novel-1");
      expect(novel).toHaveProperty("title");
      expect(novel).toHaveProperty("genre");
    });

    it("should create a novel", async () => {
      const novel = await novelsApi.create({
        title: "My New Novel",
        genre: "fantasy",
      });

      expect(novel).toHaveProperty("id");
      expect(novel.title).toBe("My New Novel");
    });

    it("should update a novel", async () => {
      const novel = await novelsApi.update("novel-1", {
        title: "Updated Title",
      });

      expect(novel.id).toBe("novel-1");
      expect(novel.title).toBe("Updated Title");
    });

    it("should delete a novel", async () => {
      // Should not throw
      await expect(novelsApi.delete("novel-1")).resolves.toBeUndefined();
    });
  });

  describe("chaptersApi", () => {
    beforeEach(() => {
      setAccessToken("test-access-token");
    });

    it("should list chapters for a novel", async () => {
      const chapters = await chaptersApi.list("novel-1");

      expect(Array.isArray(chapters)).toBe(true);
      expect(chapters.length).toBeGreaterThan(0);
      expect(chapters[0]).toHaveProperty("id");
      expect(chapters[0]).toHaveProperty("title");
    });

    it("should create a chapter", async () => {
      const chapter = await chaptersApi.create("novel-1", {
        title: "New Chapter",
      });

      expect(chapter).toHaveProperty("id");
      expect(chapter.title).toBe("New Chapter");
    });
  });

  describe("cookie sync", () => {
    it("should set narrare_auth cookie when setAccessToken is called", () => {
      const cookieSpy = vi.spyOn(Document.prototype, "cookie", "set");

      setAccessToken("token123");

      expect(cookieSpy).toHaveBeenCalledWith(
        "narrare_auth=token123; path=/; max-age=3600; samesite=lax",
      );
      cookieSpy.mockRestore();
    });

    it("should clear narrare_auth cookie when clearAccessToken is called", () => {
      const cookieSpy = vi.spyOn(Document.prototype, "cookie", "set");

      setAccessToken("token123");
      clearAccessToken();

      expect(cookieSpy).toHaveBeenCalledWith("narrare_auth=; path=/; max-age=0");
      cookieSpy.mockRestore();
    });

    it("should handle SSR gracefully when document is undefined", () => {
      vi.stubGlobal("document", undefined);

      expect(() => setAccessToken("ssr-token")).not.toThrow();
      expect(getAccessToken()).toBe("ssr-token");

      vi.unstubAllGlobals();
    });
  });

  describe("refreshAccessToken (cookie-based)", () => {
    beforeEach(() => {
      clearAccessToken();
    });

    it("should successfully refresh via cookie", async () => {
      // Calling restoreSession when no access token exists triggers refresh
      const result = await restoreSession();

      expect(result).toBe(true);
      // After successful refresh, a new access token should be stored
      expect(getAccessToken()).toBe("refreshed-access-token");
    });

    it("should store the new access token after refresh", async () => {
      expect(getAccessToken()).toBeNull();

      await restoreSession();

      expect(getAccessToken()).toBe("refreshed-access-token");
    });
  });

  describe("restoreSession", () => {
    beforeEach(() => {
      clearAccessToken();
    });

    it("should return true when no access token exists and refresh succeeds", async () => {
      expect(getAccessToken()).toBeNull();

      const result = await restoreSession();

      expect(result).toBe(true);
      expect(getAccessToken()).toBe("refreshed-access-token");
    });

    it("should return true immediately when access token already exists", async () => {
      setAccessToken("existing-token");

      const result = await restoreSession();

      expect(result).toBe(true);
      // Token should remain unchanged — no refresh call needed
      expect(getAccessToken()).toBe("existing-token");
    });

    it("should return false when refresh fails", async () => {
      // The MSW handler rejects refresh requests that include Content-Type.
      // We can't easily make refresh fail with the default handlers,
      // so we override the handler for this test.
      const { server } = await import("@/mocks/server");
      const { HttpResponse, http } = await import("msw");

      server.use(
        http.post("*/api/v1/auth/refresh", () =>
          HttpResponse.json({ detail: "No refresh token" }, { status: 401 }),
        ),
      );

      const result = await restoreSession();

      expect(result).toBe(false);
      expect(getAccessToken()).toBeNull();
    });
  });

  describe("logoutApi", () => {
    it("should call POST /api/v1/auth/logout with credentials", async () => {
      await logoutApi();

      // Should not throw — success case
    });

    it("should handle network errors gracefully", async () => {
      const { server } = await import("@/mocks/server");
      const { HttpResponse, http } = await import("msw");

      server.use(
        http.post("*/api/v1/auth/logout", () =>
          HttpResponse.json({ detail: "Server error" }, { status: 500 }),
        ),
      );

      // Should not throw despite server error
      await expect(logoutApi()).resolves.toBeUndefined();
    });
  });

  describe("fetchApi auto-refresh on 401", () => {
    it("should auto-refresh via cookie and retry on 401", async () => {
      // Start with no token — authApi.me() will get 401, then refresh + retry
      clearAccessToken();

      const user = await authApi.me();

      // After auto-refresh, the request should succeed with the refreshed token
      expect(user).toHaveProperty("id");
      expect(user).toHaveProperty("email");
      expect(getAccessToken()).toBe("refreshed-access-token");
    });
  });

  describe("ApiError mapping (status + machine-readable code)", () => {
    it("should throw ApiError with status and code for coded errors (429 BUDGET_EXCEEDED)", async () => {
      server.use(
        http.get("*/api/v1/analytics/costs", () =>
          HttpResponse.json(
            { detail: "Monthly budget exceeded", code: "BUDGET_EXCEEDED" },
            { status: 429 },
          ),
        ),
      );

      const error = await fetchApi("/analytics/costs?month=2026-10").then(
        () => null,
        (e: unknown) => e,
      );

      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.status).toBe(429);
      expect(apiError.code).toBe("BUDGET_EXCEEDED");
      expect(apiError.message).toBe("Monthly budget exceeded");
      // Still a plain Error — existing instanceof/message handling keeps working.
      expect(error).toBeInstanceOf(Error);
      expect(isBudgetExceededError(error)).toBe(true);
    });

    it("should throw ApiError with null code when the body has no code field", async () => {
      server.use(
        http.get("*/api/v1/analytics/costs", () =>
          HttpResponse.json({ detail: "Boom" }, { status: 500 }),
        ),
      );

      const error = await fetchApi("/analytics/costs?month=2026-10").then(
        () => null,
        (e: unknown) => e,
      );

      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(500);
      expect((error as ApiError).code).toBeNull();
      expect(isBudgetExceededError(error)).toBe(false);
    });

    it("should not flag non-429 or non-budget-coded errors", () => {
      expect(isBudgetExceededError(new ApiError("x", 429, "OTHER"))).toBe(false);
      expect(isBudgetExceededError(new ApiError("x", 500, "BUDGET_EXCEEDED"))).toBe(false);
      expect(isBudgetExceededError(new Error("plain"))).toBe(false);
      expect(isBudgetExceededError(null)).toBe(false);
    });
  });
});
