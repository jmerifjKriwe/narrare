import { beforeEach, describe, expect, it } from "vitest";
import {
  authApi,
  chaptersApi,
  clearAccessToken,
  getAccessToken,
  novelsApi,
  setAccessToken,
} from "./client";

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

    it("should reject me() without token", async () => {
      // MSW handler returns 401 when no Authorization header
      await expect(authApi.me()).rejects.toThrow();
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
});
