/**
 * Extraction API client tests — KB entity extraction endpoints.
 *
 * Tests:
 * 1. extractionApi.extractChapter POSTs correct URL
 * 2. extractionApi.extractChapter returns ExtractionOutput
 * 3. extractionApi.applyExtraction POSTs correct URL + body
 * 4. extractionApi.applyExtraction returns ApplyExtractionResponse
 * 5. Error handling
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import { extractionApi } from "../extraction";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockExtractionOutput = {
  results: [
    {
      item_type: "new_entity" as const,
      entity_type: "character",
      name: "Anna Schmidt",
      confidence: 0.92,
      source_text: "She walked through the old archive.",
      proposed_content: { role: "Protagonist" },
      target_entity_id: null,
      conflict_description: null,
      relationship_type: null,
      related_entity_name: null,
    },
    {
      item_type: "relationship" as const,
      entity_type: null,
      name: "Anna → Berlin",
      confidence: 0.78,
      source_text: "She lives in Berlin.",
      proposed_content: { rel_type: "resides_in" },
      target_entity_id: "entity-berlin",
      conflict_description: null,
      relationship_type: "resides_in",
      related_entity_name: "Berlin",
    },
  ],
  analysis_notes: "Found 1 new entity and 1 relationship.",
};

const mockApplyResponse = {
  created_entries: [{ id: "entry-1", name: "Anna Schmidt", entity_type: "character" }],
  updated_entries: [{ id: "entry-2", name: "Berlin", entity_type: "location" }],
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("extractionApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  describe("extractChapter", () => {
    it("should POST to /novels/:novelId/kb/extract/:chapterId", async () => {
      let capturedUrl = "";

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/extract/ch-1", ({ request }) => {
          capturedUrl = new URL(request.url).pathname;
          return HttpResponse.json(mockExtractionOutput);
        }),
      );

      const result = await extractionApi.extractChapter("novel-1", "ch-1");

      expect(capturedUrl).toContain("/novels/novel-1/kb/extract/ch-1");
      expect(result.results).toHaveLength(2);
      expect(result.analysis_notes).toBeTruthy();
    });

    it("should return structured extraction items", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/extract/ch-1", async () =>
          HttpResponse.json(mockExtractionOutput),
        ),
      );

      const result = await extractionApi.extractChapter("novel-1", "ch-1");

      const entity = result.results[0];
      expect(entity.item_type).toBe("new_entity");
      expect(entity.name).toBe("Anna Schmidt");
      expect(entity.confidence).toBe(0.92);
      expect(entity.source_text).toBeTruthy();

      const rel = result.results[1];
      expect(rel.item_type).toBe("relationship");
      expect(rel.relationship_type).toBe("resides_in");
    });

    it("should handle empty results", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/extract/ch-empty", async () =>
          HttpResponse.json({ results: [], analysis_notes: "No entities found." }),
        ),
      );

      const result = await extractionApi.extractChapter("novel-1", "ch-empty");
      expect(result.results).toHaveLength(0);
      expect(result.analysis_notes).toBe("No entities found.");
    });

    it("should handle 404 for missing chapter", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/extract/missing", async () =>
          HttpResponse.json({ detail: "Chapter not found" }, { status: 404 }),
        ),
      );

      await expect(extractionApi.extractChapter("novel-1", "missing")).rejects.toThrow();
    });
  });

  describe("applyExtraction", () => {
    it("should POST to /novels/:novelId/kb/extract/apply with items", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/extract/apply", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockApplyResponse);
        }),
      );

      const items = [
        {
          item_type: "new_entity" as const,
          name: "Anna Schmidt",
          entity_type: "character",
          proposed_content: { role: "Protagonist" },
          target_entity_id: null,
          relationship_type: null,
          related_entity_name: null,
          source_text: "She walked.",
        },
      ];

      const result = await extractionApi.applyExtraction("novel-1", items);

      expect(capturedBody.items).toHaveLength(1);
      expect(result.created_entries).toHaveLength(1);
      expect(result.created_entries[0].name).toBe("Anna Schmidt");
    });

    it("should return updated entries as well as created", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/extract/apply", async () =>
          HttpResponse.json(mockApplyResponse),
        ),
      );

      const result = await extractionApi.applyExtraction("novel-1", []);

      expect(result.updated_entries).toHaveLength(1);
      expect(result.updated_entries[0].entity_type).toBe("location");
    });

    it("should handle 500 error", async () => {
      server.use(
        http.post("*/api/v1/novels/novel-1/kb/extract/apply", async () =>
          HttpResponse.json({ detail: "Apply failed" }, { status: 500 }),
        ),
      );

      await expect(extractionApi.applyExtraction("novel-1", [])).rejects.toThrow();
    });

    it("should construct correct URL for different novel IDs", async () => {
      let capturedUrl = "";

      server.use(
        http.post("*/api/v1/novels/:novelId/kb/extract/apply", ({ request }) => {
          capturedUrl = new URL(request.url).pathname;
          return HttpResponse.json(mockApplyResponse);
        }),
      );

      await extractionApi.applyExtraction("other-novel", []);
      expect(capturedUrl).toContain("/novels/other-novel/kb/extract/apply");
    });

    // F2 Task 6 — ADR-085 apply provenance: an optional chapter id is added
    // to the apply body so KB entries can record their source chapter.
    it("should include chapter_id in the body when a chapterId is given", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/extract/apply", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockApplyResponse);
        }),
      );

      await extractionApi.applyExtraction("novel-1", [], "ch-7");

      expect(capturedBody.items).toHaveLength(0);
      expect(capturedBody.chapter_id).toBe("ch-7");
    });

    it("should omit chapter_id from the body when no chapterId is given", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/extract/apply", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockApplyResponse);
        }),
      );

      await extractionApi.applyExtraction("novel-1", []);

      expect(capturedBody).not.toHaveProperty("chapter_id");
    });
  });
});
