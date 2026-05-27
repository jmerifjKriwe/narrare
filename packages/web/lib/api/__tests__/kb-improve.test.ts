/**
 * KB Improve API client tests — entry improvement analysis and application.
 *
 * Tests:
 * 1. kbImproveApi.analyzeEntry POSTs correct URL
 * 2. kbImproveApi.analyzeEntry returns KBImproveAnalysisResponse
 * 3. kbImproveApi.applyImprovements POSTs correct URL + body
 * 4. kbImproveApi.applyImprovements returns KBImproveApplyResponse
 * 5. Error handling
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import { kbImproveApi } from "../kb-improve";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockAnalysisResponse = {
  suggestions: [
    {
      type: "add_field" as const,
      target: "personality",
      description: "Add a personality trait section.",
      proposed_content: "Brave and resourceful, but sometimes impulsive.",
      related_entity_id: null,
      related_entity_name: null,
      confidence: 0.88,
      reasoning: "Characters with personality traits feel more three-dimensional.",
      suggestion_id: 1,
    },
    {
      type: "connect" as const,
      target: "Berlin",
      description: "Connect to the location entity.",
      proposed_content: null,
      related_entity_id: "entity-berlin",
      related_entity_name: "Berlin",
      confidence: 0.75,
      reasoning: "The character mentions living in Berlin.",
      suggestion_id: 2,
    },
    {
      type: "expand" as const,
      target: "backstory",
      description: "Expand the backstory section.",
      proposed_content: "Add details about childhood.",
      related_entity_id: null,
      related_entity_name: null,
      confidence: 0.65,
      reasoning: "The backstory section is very brief.",
      suggestion_id: 3,
    },
  ],
  overall_assessment: "Entry has potential but needs more depth.",
  completeness_score: 0.55,
};

const mockApplyResponse = {
  success: true,
  entry_id: "entry-1",
  applied_count: 2,
  message: "Applied 2 of 2 suggestions.",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("kbImproveApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  describe("analyzeEntry", () => {
    it("should POST to /novels/:novelId/kb/entities/:entryId/improve", async () => {
      let capturedUrl = "";

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/entities/entry-1/improve", ({ request }) => {
          capturedUrl = new URL(request.url).pathname;
          return HttpResponse.json(mockAnalysisResponse);
        }),
      );

      const result = await kbImproveApi.analyzeEntry("novel-1", "entry-1");

      expect(capturedUrl).toContain("/novels/novel-1/kb/entities/entry-1/improve");
      expect(result.suggestions).toHaveLength(3);
      expect(result.completeness_score).toBe(0.55);
    });

    it("should return suggestions with correct structure", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/entities/entry-1/improve", async () =>
          HttpResponse.json(mockAnalysisResponse),
        ),
      );

      const result = await kbImproveApi.analyzeEntry("novel-1", "entry-1");

      const suggestion = result.suggestions[0];
      expect(suggestion.type).toBe("add_field");
      expect(suggestion.target).toBe("personality");
      expect(suggestion.confidence).toBe(0.88);
      expect(suggestion.suggestion_id).toBe(1);
    });

    it("should return connect suggestion with related entity", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/entities/entry-1/improve", async () =>
          HttpResponse.json(mockAnalysisResponse),
        ),
      );

      const result = await kbImproveApi.analyzeEntry("novel-1", "entry-1");

      const connect = result.suggestions[1];
      expect(connect.type).toBe("connect");
      expect(connect.related_entity_id).toBe("entity-berlin");
      expect(connect.related_entity_name).toBe("Berlin");
    });

    it("should return overall assessment", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/entities/entry-1/improve", async () =>
          HttpResponse.json(mockAnalysisResponse),
        ),
      );

      const result = await kbImproveApi.analyzeEntry("novel-1", "entry-1");
      expect(result.overall_assessment).toBeTruthy();
    });

    it("should handle empty suggestions", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/entities/entry-1/improve", async () =>
          HttpResponse.json({
            suggestions: [],
            overall_assessment: "Entry is already complete.",
            completeness_score: 1.0,
          }),
        ),
      );

      const result = await kbImproveApi.analyzeEntry("novel-1", "entry-1");
      expect(result.suggestions).toHaveLength(0);
      expect(result.completeness_score).toBe(1.0);
    });

    it("should handle 500 error", async () => {
      server.use(
        http.post("*/api/v1/novels/:novelId/kb/entities/:entryId/improve", async () =>
          HttpResponse.json({ detail: "Analysis failed" }, { status: 500 }),
        ),
      );

      await expect(kbImproveApi.analyzeEntry("novel-1", "entry-1")).rejects.toThrow();
    });
  });

  describe("applyImprovements", () => {
    it("should POST to /novels/:novelId/kb/entities/:entryId/improve/apply with suggestion_ids", async () => {
      let capturedUrl = "";
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post(
          "*/api/v1/novels/novel-1/kb/entities/entry-1/improve/apply",
          async ({ request }) => {
            capturedUrl = new URL(request.url).pathname;
            capturedBody = (await request.json()) as Record<string, unknown>;
            return HttpResponse.json(mockApplyResponse);
          },
        ),
      );

      const result = await kbImproveApi.applyImprovements("novel-1", "entry-1", [1, 2]);

      expect(capturedUrl).toContain("/novels/novel-1/kb/entities/entry-1/improve/apply");
      expect(capturedBody.suggestion_ids).toEqual([1, 2]);
      expect(result.success).toBe(true);
      expect(result.applied_count).toBe(2);
    });

    it("should return apply response with entry_id and message", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/entities/entry-1/improve/apply", async () =>
          HttpResponse.json(mockApplyResponse),
        ),
      );

      const result = await kbImproveApi.applyImprovements("novel-1", "entry-1", [1, 2]);

      expect(result.entry_id).toBe("entry-1");
      expect(result.message).toContain("Applied");
    });

    it("should handle empty suggestion_ids", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/entities/entry-1/improve/apply", async () =>
          HttpResponse.json({
            success: true,
            entry_id: "entry-1",
            applied_count: 0,
            message: "No suggestions applied.",
          }),
        ),
      );

      const result = await kbImproveApi.applyImprovements("novel-1", "entry-1", []);
      expect(result.applied_count).toBe(0);
    });

    it("should handle 404 for missing entry", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/entities/missing/improve/apply", async () =>
          HttpResponse.json({ detail: "Entry not found" }, { status: 404 }),
        ),
      );

      await expect(kbImproveApi.applyImprovements("novel-1", "missing", [1])).rejects.toThrow();
    });
  });
});
