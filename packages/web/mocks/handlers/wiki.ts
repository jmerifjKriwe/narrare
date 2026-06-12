/**
 * MSW handlers for Wiki API endpoints.
 *
 * Covers:
 *   GET  /api/v1/novels/:novelId/wiki/index
 *   GET  /api/v1/novels/:novelId/wiki/summaries
 *   GET  /api/v1/novels/:novelId/wiki/summaries/:entityId
 *   GET  /api/v1/novels/:novelId/wiki/chapters/:chapterId/summary
 *   POST /api/v1/novels/:novelId/wiki/summaries/:entityId/refresh
 *   POST /api/v1/novels/:novelId/wiki/mark-stale
 */

import { HttpResponse, http } from "msw";

// ---------------------------------------------------------------------------
// Mock Data
// ---------------------------------------------------------------------------

const mockWikiIndex = {
  novel_id: "novel-1",
  total_summaries: 20,
  fresh_count: 12,
  stale_count: 3,
  pending_count: 5,
  last_generated_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
};

const mockSummaries = [
  {
    id: "ws-1",
    novel_id: "novel-1",
    entity_id: "kb-entry-1",
    narrative_summary: "A brave hero who fights for justice and freedom.",
    role_in_story: "Protagonist",
    key_attributes: ["brave", "determined"],
    relationships: null,
    chapter_references: null,
    character_arc: "From farm boy to legendary warrior",
    status: "fresh" as const,
    version: 3,
    generated_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    refreshed_at: null,
  },
];

const mockChapterSummary = {
  id: "wcs-1",
  chapter_id: "chapter-1",
  narrative_summary:
    "In this chapter, the protagonist discovers a hidden passage beneath the castle.",
  key_events: [
    "Discovery of hidden passage",
    "Confrontation with the guard",
    "Escape through tunnels",
  ],
  entities_involved: [
    { name: "John Smith", entity_id: "kb-entry-1" },
    { name: "Castle Black", entity_id: "kb-entry-2" },
  ],
  themes: ["Betrayal", "Redemption"],
  emotional_arc: "Rising tension → Climax",
  status: "fresh" as const,
  version: 2,
  generated_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
};

const mockRefreshResponse = {
  summary_id: "ws-1",
  status: "completed",
  message: "Summary refreshed successfully",
};

const mockMarkStaleResponse = {
  count: 3,
};

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

export const handlers = [
  // GET /api/v1/novels/:novelId/wiki/index
  http.get("*/api/v1/novels/:novelId/wiki/index", ({ params }) => {
    const { novelId } = params;
    return HttpResponse.json({
      ...mockWikiIndex,
      novel_id: novelId,
    });
  }),

  // GET /api/v1/novels/:novelId/wiki/summaries
  http.get("*/api/v1/novels/:novelId/wiki/summaries", ({ request }) => {
    const url = new URL(request.url);
    const entityIds = url.searchParams.get("entity_ids");
    const items = entityIds
      ? mockSummaries.filter((s) => entityIds.split(",").includes(s.entity_id))
      : mockSummaries;
    return HttpResponse.json({ items, total: items.length });
  }),

  // GET /api/v1/novels/:novelId/wiki/summaries/:entityId
  http.get("*/api/v1/novels/:novelId/wiki/summaries/:entityId", ({ params }) => {
    const { novelId, entityId } = params;
    const summary = mockSummaries.find((s) => s.entity_id === entityId);
    if (!summary) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json({ ...summary, novel_id: novelId });
  }),

  // GET /api/v1/novels/:novelId/wiki/chapters/:chapterId/summary
  http.get("*/api/v1/novels/:novelId/wiki/chapters/:chapterId/summary", ({ params }) => {
    const { novelId, chapterId } = params;
    return HttpResponse.json({ ...mockChapterSummary, novel_id: novelId, chapter_id: chapterId });
  }),

  // POST /api/v1/novels/:novelId/wiki/summaries/:entityId/refresh
  http.post("*/api/v1/novels/:novelId/wiki/summaries/:entityId/refresh", () => {
    return HttpResponse.json(mockRefreshResponse);
  }),

  // POST /api/v1/novels/:novelId/wiki/mark-stale
  http.post("*/api/v1/novels/:novelId/wiki/mark-stale", () => {
    return HttpResponse.json(mockMarkStaleResponse);
  }),
];
