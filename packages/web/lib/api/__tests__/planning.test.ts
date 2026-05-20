import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import {
  confirmRemap,
  getOutline,
  getStoryboard,
  getSyncStatus,
  previewRemap,
  updateOutline,
} from "../planning";

/**
 * Unit tests for the planning API client.
 *
 * Follows the same pattern as client.test.ts and generation.test.ts:
 * - Uses MSW server to intercept requests
 * - Verifies correct URL construction, method, and request body
 * - Tests all 6 API functions
 */

// ---------------------------------------------------------------------------
// MSW handlers for planning endpoints
// ---------------------------------------------------------------------------

const planningHandlers = [
  http.get("*/api/v1/planning/storyboard/:novelId", async () => {
    return HttpResponse.json({
      structure_type: "three_act",
      stages: [
        {
          stage_id: "act-1",
          stage_name: "Act 1: Setup",
          chapters: [
            {
              chapter_id: "ch-1",
              title: "The Beginning",
              word_count: 2500,
              sync_status: "on_track",
              position: 0,
            },
          ],
        },
        {
          stage_id: "act-2",
          stage_name: "Act 2: Confrontation",
          chapters: [],
        },
        {
          stage_id: "act-3",
          stage_name: "Act 3: Resolution",
          chapters: [],
        },
      ],
    });
  }),

  http.get("*/api/v1/planning/storyboard/:novelId/sync", async () => {
    return HttpResponse.json([
      { chapter_id: "ch-1", status: "on_track" },
      { chapter_id: "ch-2", status: "deviated" },
    ]);
  }),

  http.get("*/api/v1/planning/outlines/:novelId/:chapterId", async ({ params }) => {
    return HttpResponse.json({
      id: "outline-1",
      chapter_id: params.chapterId,
      stage_assignment: "act-1",
      planned_beats: [
        { title: "Opening Hook", description: "Start with action", completed: false },
        { title: "Meet Protagonist", description: "Introduce main character", completed: true },
      ],
      outline_notes: "Focus on tension",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
    });
  }),

  http.put("*/api/v1/planning/outlines/:novelId/:chapterId", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id: "outline-1",
      chapter_id: params.chapterId,
      stage_assignment: body.stage_assignment ?? "act-1",
      planned_beats: body.planned_beats ?? [],
      outline_notes: body.outline_notes ?? "",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
    });
  }),

  http.post("*/api/v1/planning/storyboard/:novelId/remap", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const confirmed = body.confirm as boolean;
    return HttpResponse.json({
      new_structure: body.new_structure,
      remapped: [
        {
          chapter_id: "ch-1",
          chapter_title: "Chapter One",
          old_stage: "Act 1",
          new_stage: "Exposition",
        },
      ],
      confirmed,
    });
  }),
];

describe("Planning API client", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
    server.use(...planningHandlers);
  });

  describe("getStoryboard", () => {
    it("should GET /planning/storyboard/:novelId and return storyboard", async () => {
      const result = await getStoryboard("novel-1");

      expect(result.structure_type).toBe("three_act");
      expect(result.stages).toHaveLength(3);
      expect(result.stages[0].stage_id).toBe("act-1");
      expect(result.stages[0].chapters).toHaveLength(1);
      expect(result.stages[0].chapters[0].title).toBe("The Beginning");
    });
  });

  describe("getSyncStatus", () => {
    it("should GET /planning/storyboard/:novelId/sync and return status array", async () => {
      const result = await getSyncStatus("novel-1");

      expect(Array.isArray(result)).toBe(true);
      expect(result).toHaveLength(2);
      expect(result[0].chapter_id).toBe("ch-1");
      expect(result[0].status).toBe("on_track");
      expect(result[1].status).toBe("deviated");
    });
  });

  describe("getOutline", () => {
    it("should GET /planning/outlines/:novelId/:chapterId and return outline", async () => {
      const result = await getOutline("novel-1", "ch-1");

      expect(result.chapter_id).toBe("ch-1");
      expect(result.stage_assignment).toBe("act-1");
      expect(result.planned_beats).toHaveLength(2);
      expect(result.planned_beats[0].title).toBe("Opening Hook");
      expect(result.outline_notes).toBe("Focus on tension");
    });
  });

  describe("updateOutline", () => {
    it("should PUT /planning/outlines/:novelId/:chapterId with correct body", async () => {
      const result = await updateOutline("novel-1", "ch-1", {
        stage_assignment: "act-2",
      });

      expect(result.chapter_id).toBe("ch-1");
      expect(result.stage_assignment).toBe("act-2");
    });

    it("should send planned_beats and notes in request body", async () => {
      const beats = [{ title: "New Beat", description: "A new beat", completed: false }];
      const result = await updateOutline("novel-1", "ch-1", {
        stage_assignment: "act-1",
        planned_beats: beats,
        outline_notes: "Updated notes",
      });

      expect(result.planned_beats).toEqual(beats);
    });
  });

  describe("previewRemap", () => {
    it("should POST /planning/storyboard/:novelId/remap with confirm=false", async () => {
      const result = await previewRemap("novel-1", "five_act");

      expect(result.new_structure).toBe("five_act");
      expect(result.confirmed).toBe(false);
      expect(result.remapped).toHaveLength(1);
      expect(result.remapped[0].chapter_title).toBe("Chapter One");
    });
  });

  describe("confirmRemap", () => {
    it("should POST /planning/storyboard/:novelId/remap with confirm=true", async () => {
      const result = await confirmRemap("novel-1", "five_act");

      expect(result.new_structure).toBe("five_act");
      expect(result.confirmed).toBe(true);
      expect(result.remapped).toHaveLength(1);
    });
  });

  describe("URL construction", () => {
    it("should construct correct storyboard URL", async () => {
      let capturedUrl = "";
      server.use(
        http.get("*/api/v1/planning/storyboard/:novelId", ({ request }) => {
          capturedUrl = new URL(request.url).pathname;
          return HttpResponse.json({
            structure_type: "three_act",
            stages: [],
          });
        }),
      );

      await getStoryboard("my-novel-id");
      expect(capturedUrl).toContain("/planning/storyboard/my-novel-id");
    });

    it("should construct correct outline URL with novel and chapter IDs", async () => {
      let capturedUrl = "";
      server.use(
        http.get("*/api/v1/planning/outlines/:novelId/:chapterId", ({ request }) => {
          capturedUrl = new URL(request.url).pathname;
          return HttpResponse.json({
            id: "o-1",
            chapter_id: "ch-x",
            stage_assignment: "",
            planned_beats: [],
            outline_notes: "",
            created_at: "",
            updated_at: "",
          });
        }),
      );

      await getOutline("novel-42", "chapter-99");
      expect(capturedUrl).toContain("/planning/outlines/novel-42/chapter-99");
    });
  });
});
