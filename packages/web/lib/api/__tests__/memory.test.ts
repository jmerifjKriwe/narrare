/**
 * Memory API client tests — feedback, preferences, and analysis endpoints.
 *
 * Tests:
 * 1. memoryApi.recordFeedback POSTs /memory/feedback
 * 2. memoryApi.getPreferences GETs /memory/preferences
 * 3. memoryApi.resetPreferences DELETEs /memory/preferences
 * 4. memoryApi.triggerAnalysis POSTs /memory/analyze
 * 5. Error handling
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import { memoryApi } from "../memory";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockFeedbackResponse = {
  id: "fb-1",
  action: "accept",
  created_at: "2026-05-27T10:00:00Z",
};

const mockPreferenceProfile = {
  user_id: "user-1",
  project_id: "proj-1",
  event_count: 42,
  confidence: 0.85,
  style: { tone: "dramatic", pov: "third_person" },
  content: { genre: "fantasy" },
  constraints: ["Avoid clichés"],
  last_updated: "2026-05-27T09:00:00Z",
};

const mockResetResponse = {
  message: "Preferences reset successfully.",
  deleted_count: 42,
};

const mockAnalyzeResponse = {
  id: "analysis-1",
  user_id: "user-1",
  project_id: "proj-1",
  confidence: 0.9,
  summary: "User prefers dramatic fantasy with third-person POV.",
  style_patterns: ["dramatic tone", "descriptive prose"],
  content_patterns: ["fantasy settings", "complex characters"],
  avoidance_patterns: ["clichés", "deus ex machina"],
  event_count_at_analysis: 42,
  created_at: "2026-05-27T10:00:00Z",
  updated_at: "2026-05-27T10:00:00Z",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("memoryApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  describe("recordFeedback", () => {
    it("should POST to /memory/feedback with feedback data", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/memory/feedback", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockFeedbackResponse);
        }),
      );

      const result = await memoryApi.recordFeedback({
        action: "accept",
        suggestion_id: "sug-1",
        intent: "generation",
        suggestion_text: "The dragon roared.",
        project_id: "proj-1",
      });

      expect(capturedBody.action).toBe("accept");
      expect(capturedBody.suggestion_id).toBe("sug-1");
      expect(capturedBody.intent).toBe("generation");
      expect(result.id).toBe("fb-1");
    });

    it("should send optional fields when provided", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/memory/feedback", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockFeedbackResponse);
        }),
      );

      await memoryApi.recordFeedback({
        action: "modify",
        suggestion_id: "sug-2",
        intent: "planning",
        suggestion_text: "Original text.",
        modification: "Modified text.",
        rating: 4,
        project_id: "proj-1",
        chapter_id: "ch-1",
      });

      expect(capturedBody.modification).toBe("Modified text.");
      expect(capturedBody.rating).toBe(4);
      expect(capturedBody.chapter_id).toBe("ch-1");
    });

    it("should handle 400 error for invalid feedback", async () => {
      server.use(
        http.post("*/api/v1/memory/feedback", async () =>
          HttpResponse.json({ detail: "Invalid action" }, { status: 400 }),
        ),
      );

      await expect(
        memoryApi.recordFeedback({
          action: "accept",
          suggestion_id: "sug-1",
          intent: "generation",
          suggestion_text: "test",
          project_id: "proj-1",
        }),
      ).rejects.toThrow();
    });
  });

  describe("getPreferences", () => {
    it("should GET /memory/preferences with project_id query param", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/memory/preferences", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json(mockPreferenceProfile);
        }),
      );

      const result = await memoryApi.getPreferences("proj-1");

      const url = new URL(capturedUrl);
      expect(url.searchParams.get("project_id")).toBe("proj-1");
      expect(result.event_count).toBe(42);
      expect(result.confidence).toBe(0.85);
    });

    it("should return style and content preferences", async () => {
      server.use(
        http.get("*/api/v1/memory/preferences", async () =>
          HttpResponse.json(mockPreferenceProfile),
        ),
      );

      const result = await memoryApi.getPreferences("proj-1");

      expect(result.style).toEqual({ tone: "dramatic", pov: "third_person" });
      expect(result.content).toEqual({ genre: "fantasy" });
      expect(result.constraints).toContain("Avoid clichés");
    });
  });

  describe("resetPreferences", () => {
    it("should DELETE /memory/preferences with project_id query param", async () => {
      let capturedMethod = "";
      let capturedUrl = "";

      server.use(
        http.delete("*/api/v1/memory/preferences", ({ request }) => {
          capturedMethod = request.method;
          capturedUrl = request.url;
          return HttpResponse.json(mockResetResponse);
        }),
      );

      const result = await memoryApi.resetPreferences("proj-1");

      expect(capturedMethod).toBe("DELETE");
      const url = new URL(capturedUrl);
      expect(url.searchParams.get("project_id")).toBe("proj-1");
      expect(result.message).toContain("reset");
      expect(result.deleted_count).toBe(42);
    });
  });

  describe("triggerAnalysis", () => {
    it("should POST to /memory/analyze with project_id", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/memory/analyze", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockAnalyzeResponse);
        }),
      );

      const result = await memoryApi.triggerAnalysis({ project_id: "proj-1" });

      expect(capturedBody.project_id).toBe("proj-1");
      expect(result.confidence).toBe(0.9);
      expect(result.style_patterns).toHaveLength(2);
      expect(result.event_count_at_analysis).toBe(42);
    });

    it("should return analysis with avoidance patterns", async () => {
      server.use(
        http.post("*/api/v1/memory/analyze", async () => HttpResponse.json(mockAnalyzeResponse)),
      );

      const result = await memoryApi.triggerAnalysis({ project_id: "proj-1" });

      expect(result.avoidance_patterns).toContain("clichés");
      expect(result.summary).toBeTruthy();
    });

    it("should handle 500 error", async () => {
      server.use(
        http.post("*/api/v1/memory/analyze", async () =>
          HttpResponse.json({ detail: "Analysis failed" }, { status: 500 }),
        ),
      );

      await expect(memoryApi.triggerAnalysis({ project_id: "proj-1" })).rejects.toThrow();
    });
  });
});
