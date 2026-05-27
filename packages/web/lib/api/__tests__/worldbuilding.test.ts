/**
 * Worldbuilding API client tests — analysis and apply endpoints.
 *
 * Tests:
 * 1. worldbuildingApi.analyze POSTs correct URL + body
 * 2. worldbuildingApi.analyze returns WorldbuildingAnalysisResponse
 * 3. worldbuildingApi.applyConnections POSTs correct URL + body
 * 4. worldbuildingApi.applyConnections returns WorldbuildingApplyResponse
 * 5. Error handling
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import { worldbuildingApi } from "../worldbuilding";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockAnalysisResponse = {
  novel_id: "novel-1",
  entity_count: 15,
  gap_findings: [
    {
      entity_id: "entity-1",
      entity_name: "Anna",
      entity_type: "character",
      gap_type: "missing_field" as const,
      field_key: "personality",
      description: "No personality traits defined.",
      related_entity_type: null,
      story_relevance: 8,
      severity: "major" as const,
    },
    {
      entity_id: null,
      entity_name: null,
      entity_type: null,
      gap_type: "missing_entity" as const,
      field_key: null,
      description: "No antagonist defined.",
      related_entity_type: "character",
      story_relevance: 9,
      severity: "critical" as const,
    },
  ],
  connection_suggestions: [
    {
      finding_index: 0,
      source_entity_id: "entity-1",
      source_entity_name: "Anna",
      source_entity_type: "character",
      target_entity_id: "entity-2",
      target_entity_name: "Berlin",
      target_entity_type: "location",
      suggested_rel_type: "resides_in",
      inverse_rel_type: "resident_of",
      reasoning: "Anna mentions living in Berlin.",
      confidence: 0.82,
      story_relevance: 5,
    },
  ],
  consistency_issues: [
    {
      finding_index: 0,
      category: "timeline" as const,
      entity_ids: ["entity-1"],
      entity_names: ["Anna"],
      description: "Age inconsistency detected.",
      contradiction: "Born 1990 but said to be 25 in 2020.",
      suggested_resolution: "Adjust birth year to 1995.",
      severity: "major" as const,
      confidence: 0.9,
    },
  ],
  worldbuilding_score: 0.65,
  overall_assessment: "Good foundation with some gaps to address.",
  summary: { missing_field: 1, missing_entity: 1, major: 1, critical: 1 },
  analyzed_at: "2026-05-27T12:00:00Z",
};

const mockApplyResponse = {
  success: true,
  created_count: 1,
  failed_count: 0,
  errors: [],
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("worldbuildingApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  describe("analyze", () => {
    it("should POST to /novels/:novelId/kb/worldbuilding/analyze", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/worldbuilding/analyze", async () =>
          HttpResponse.json(mockAnalysisResponse),
        ),
      );

      const result = await worldbuildingApi.analyze("novel-1");

      expect(result.novel_id).toBe("novel-1");
      expect(result.entity_count).toBe(15);
      expect(result.worldbuilding_score).toBe(0.65);
    });

    it("should send request body with options when provided", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/worldbuilding/analyze", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockAnalysisResponse);
        }),
      );

      await worldbuildingApi.analyze("novel-1", {
        entity_types: ["character"],
        include_gaps: true,
        include_connections: false,
        include_consistency: true,
        max_findings: 10,
        refresh: true,
      });

      expect(capturedBody.entity_types).toEqual(["character"]);
      expect(capturedBody.include_gaps).toBe(true);
      expect(capturedBody.include_connections).toBe(false);
      expect(capturedBody.max_findings).toBe(10);
      expect(capturedBody.refresh).toBe(true);
    });

    it("should send empty object body when no request provided", async () => {
      let capturedBody: unknown = null;

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/worldbuilding/analyze", async ({ request }) => {
          capturedBody = await request.json();
          return HttpResponse.json(mockAnalysisResponse);
        }),
      );

      await worldbuildingApi.analyze("novel-1");
      expect(capturedBody).toEqual({});
    });

    it("should return gap findings with correct structure", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/worldbuilding/analyze", async () =>
          HttpResponse.json(mockAnalysisResponse),
        ),
      );

      const result = await worldbuildingApi.analyze("novel-1");

      expect(result.gap_findings).toHaveLength(2);
      expect(result.gap_findings[0].gap_type).toBe("missing_field");
      expect(result.gap_findings[0].severity).toBe("major");
      expect(result.gap_findings[1].gap_type).toBe("missing_entity");
      expect(result.gap_findings[1].story_relevance).toBe(9);
    });

    it("should return connection suggestions with correct structure", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/worldbuilding/analyze", async () =>
          HttpResponse.json(mockAnalysisResponse),
        ),
      );

      const result = await worldbuildingApi.analyze("novel-1");

      expect(result.connection_suggestions).toHaveLength(1);
      const suggestion = result.connection_suggestions[0];
      expect(suggestion.source_entity_name).toBe("Anna");
      expect(suggestion.target_entity_name).toBe("Berlin");
      expect(suggestion.suggested_rel_type).toBe("resides_in");
      expect(suggestion.confidence).toBe(0.82);
    });

    it("should return consistency issues with correct structure", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/worldbuilding/analyze", async () =>
          HttpResponse.json(mockAnalysisResponse),
        ),
      );

      const result = await worldbuildingApi.analyze("novel-1");

      expect(result.consistency_issues).toHaveLength(1);
      const issue = result.consistency_issues[0];
      expect(issue.category).toBe("timeline");
      expect(issue.severity).toBe("major");
      expect(issue.contradiction).toBeTruthy();
      expect(issue.suggested_resolution).toBeTruthy();
    });

    it("should handle empty analysis results", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/worldbuilding/analyze", async () =>
          HttpResponse.json({
            novel_id: "novel-1",
            entity_count: 0,
            gap_findings: [],
            connection_suggestions: [],
            consistency_issues: [],
            worldbuilding_score: 1.0,
            overall_assessment: "No entities to analyze.",
            summary: {},
            analyzed_at: "2026-05-27T12:00:00Z",
          }),
        ),
      );

      const result = await worldbuildingApi.analyze("novel-1");
      expect(result.gap_findings).toHaveLength(0);
      expect(result.connection_suggestions).toHaveLength(0);
      expect(result.consistency_issues).toHaveLength(0);
    });

    it("should handle 500 error", async () => {
      server.use(
        http.post("*/api/v1/novels/:novelId/kb/worldbuilding/analyze", async () =>
          HttpResponse.json({ detail: "Analysis failed" }, { status: 500 }),
        ),
      );

      await expect(worldbuildingApi.analyze("novel-1")).rejects.toThrow();
    });
  });

  describe("applyConnections", () => {
    it("should POST to /novels/:novelId/kb/worldbuilding/apply with body", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/worldbuilding/apply", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockApplyResponse);
        }),
      );

      const result = await worldbuildingApi.applyConnections("novel-1", {
        finding_indices: [0],
        analysis: mockAnalysisResponse,
      });

      expect(capturedBody.finding_indices).toEqual([0]);
      expect(capturedBody.analysis).toBeDefined();
      expect(result.success).toBe(true);
      expect(result.created_count).toBe(1);
      expect(result.failed_count).toBe(0);
    });

    it("should return errors array on partial failure", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/worldbuilding/apply", async () =>
          HttpResponse.json({
            success: false,
            created_count: 0,
            failed_count: 1,
            errors: ["Entity not found for suggestion at index 0"],
          }),
        ),
      );

      const result = await worldbuildingApi.applyConnections("novel-1", {
        finding_indices: [99],
        analysis: mockAnalysisResponse,
      });

      expect(result.success).toBe(false);
      expect(result.errors).toHaveLength(1);
    });

    it("should handle 404 error", async () => {
      server.use(
        http.post("*/api/v1/novels/missing/kb/worldbuilding/apply", async () =>
          HttpResponse.json({ detail: "Novel not found" }, { status: 404 }),
        ),
      );

      await expect(
        worldbuildingApi.applyConnections("missing", {
          finding_indices: [],
          analysis: mockAnalysisResponse,
        }),
      ).rejects.toThrow();
    });
  });
});
