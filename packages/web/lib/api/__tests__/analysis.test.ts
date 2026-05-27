/**
 * Analysis API client tests — beta reader analysis endpoints.
 *
 * Tests:
 * 1. analysisApi.analyze POSTs correct URL + body
 * 2. analysisApi.analyze returns BetaReaderResponse
 * 3. analysisApi.deepDive POSTs correct URL + body
 * 4. analysisApi.deepDive returns BetaReaderDeepDiveResponse
 * 5. Error handling (500)
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { analysisApi } from "../analysis";
import { setAccessToken } from "../client";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockBetaReaderResponse = {
  novel_id: "novel-1",
  chapter_ids: ["ch-1", "ch-2"],
  total_word_count: 5200,
  strengths: [
    {
      category: "character" as const,
      title: "Strong protagonist voice",
      description: "The narrative voice feels authentic.",
      text_excerpt: "She opened the door.",
    },
  ],
  feedback: [
    {
      category: "pacing" as const,
      severity: "moderate" as const,
      location: "ch-2",
      title: "Middle section drags",
      description: "Pacing slows after the inciting incident.",
      suggestion: "Consider tightening the dialogue.",
      text_excerpt: "They talked for a while.",
    },
  ],
  questions: [
    {
      category: "plot" as const,
      location: "ch-1",
      question: "Why does the protagonist ignore the letter?",
      context: "The letter seems important to the plot.",
    },
  ],
  overall: {
    summary: "A solid opening with room for improvement.",
    reader_engagement: 7.5,
    emotional_impact: 6.0,
    pacing_score: 5.5,
    prose_quality: 8.0,
    plot_progression: 7.0,
    character_development: 8.5,
  },
  analyzed_at: "2026-05-27T10:00:00Z",
  cache_key: "cache-abc123",
};

const mockDeepDiveResponse = {
  novel_id: "novel-1",
  category: "pacing" as const,
  detailed_feedback: [
    {
      category: "pacing" as const,
      severity: "critical" as const,
      location: "ch-2",
      title: "Pacing breakdown in Act 2",
      description: "The tension drops significantly.",
      suggestion: "Add a ticking clock element.",
      text_excerpt: "Nothing happened for pages.",
    },
  ],
  revision_suggestions: ["Introduce a deadline in chapter 2."],
  category_score: 4.5,
  analyzed_at: "2026-05-27T10:05:00Z",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("analysisApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  describe("analyze", () => {
    it("should POST to /analysis/beta-reader with correct query params and body", async () => {
      let capturedUrl = "";
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/analysis/beta-reader", async ({ request }) => {
          capturedUrl = `${new URL(request.url).pathname}?${new URL(request.url).searchParams.toString()}`;
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockBetaReaderResponse);
        }),
      );

      const request = {
        chapter_ids: ["ch-1", "ch-2"],
        phase: "full" as const,
      };

      const result = await analysisApi.analyze("novel-1", request);

      expect(capturedUrl).toContain("novel_id=novel-1");
      expect(capturedBody.phase).toBe("full");
      expect(capturedBody.chapter_ids).toEqual(["ch-1", "ch-2"]);
      expect(result.novel_id).toBe("novel-1");
      expect(result.cache_key).toBe("cache-abc123");
    });

    it("should return strengths, feedback, questions, and overall assessment", async () => {
      server.use(
        http.post("*/api/v1/analysis/beta-reader", async () =>
          HttpResponse.json(mockBetaReaderResponse),
        ),
      );

      const result = await analysisApi.analyze("novel-1", {
        chapter_ids: ["ch-1"],
        phase: "full",
      });

      expect(result.strengths).toHaveLength(1);
      expect(result.strengths[0].category).toBe("character");
      expect(result.feedback).toHaveLength(1);
      expect(result.feedback[0].severity).toBe("moderate");
      expect(result.questions).toHaveLength(1);
      expect(result.questions[0].question).toContain("letter");
      expect(result.overall.reader_engagement).toBe(7.5);
      expect(result.total_word_count).toBe(5200);
    });

    it("should pass categories and deepdive params in request body", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/analysis/beta-reader", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockBetaReaderResponse);
        }),
      );

      await analysisApi.analyze("novel-1", {
        chapter_ids: ["ch-1"],
        phase: "deepdive",
        categories: ["plot", "pacing"],
        deepdive_category: "pacing",
        refresh: true,
      });

      expect(capturedBody.phase).toBe("deepdive");
      expect(capturedBody.categories).toEqual(["plot", "pacing"]);
      expect(capturedBody.deepdive_category).toBe("pacing");
      expect(capturedBody.refresh).toBe(true);
    });

    it("should handle 500 error", async () => {
      server.use(
        http.post("*/api/v1/analysis/beta-reader", async () =>
          HttpResponse.json({ detail: "Internal server error" }, { status: 500 }),
        ),
      );

      await expect(
        analysisApi.analyze("novel-1", { chapter_ids: ["ch-1"], phase: "full" }),
      ).rejects.toThrow();
    });
  });

  describe("deepDive", () => {
    it("should POST to /analysis/beta-reader/deep-dive with correct params", async () => {
      let capturedUrl = "";
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/analysis/beta-reader/deep-dive", async ({ request }) => {
          capturedUrl =
            new URL(request.url).pathname + "?" + new URL(request.url).searchParams.toString();
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockDeepDiveResponse);
        }),
      );

      const result = await analysisApi.deepDive("novel-1", {
        chapter_ids: ["ch-1", "ch-2"],
        category: "pacing",
        cache_key: "cache-abc123",
      });

      expect(capturedUrl).toContain("novel_id=novel-1");
      expect(capturedBody.category).toBe("pacing");
      expect(capturedBody.cache_key).toBe("cache-abc123");
      expect(result.category).toBe("pacing");
      expect(result.category_score).toBe(4.5);
    });

    it("should return detailed feedback and revision suggestions", async () => {
      server.use(
        http.post("*/api/v1/analysis/beta-reader/deep-dive", async () =>
          HttpResponse.json(mockDeepDiveResponse),
        ),
      );

      const result = await analysisApi.deepDive("novel-1", {
        chapter_ids: ["ch-1"],
        category: "pacing",
        cache_key: "cache-abc123",
      });

      expect(result.detailed_feedback).toHaveLength(1);
      expect(result.detailed_feedback[0].severity).toBe("critical");
      expect(result.revision_suggestions).toHaveLength(1);
      expect(result.revision_suggestions[0]).toContain("deadline");
    });

    it("should handle 404 error", async () => {
      server.use(
        http.post("*/api/v1/analysis/beta-reader/deep-dive", async () =>
          HttpResponse.json({ detail: "Analysis not found" }, { status: 404 }),
        ),
      );

      await expect(
        analysisApi.deepDive("novel-1", {
          chapter_ids: ["ch-1"],
          category: "pacing",
          cache_key: "missing",
        }),
      ).rejects.toThrow();
    });
  });
});
