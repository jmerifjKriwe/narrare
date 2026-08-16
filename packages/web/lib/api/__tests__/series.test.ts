/**
 * Series API client tests — covers all `seriesApi` methods.
 *
 * Pattern: MSW request interception (see lib/api/__tests__/tasks.test.ts),
 * NOT global.fetch mutation. Verifies HTTP method, path, request body, and
 * return shape for every endpoint shipped in Series Slice 3:
 *   - CRUD: list, get, create, update, delete
 *   - Novels: listNovels, previewJoin, applyJoin, removeNovel, reorderNovels
 *   - Settings: getSettings, updateSettings
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import { seriesApi } from "../series";

// ---------------------------------------------------------------------------
// Fixtures (mirror apps/api/narrare/series/schemas.py shapes)
// ---------------------------------------------------------------------------

const mockSeries = {
  id: "series-1",
  user_id: "user-1",
  title: "The Expanse",
  subtitle: "A space opera",
  description: "Sci-fi series.",
  genre: "sci-fi",
  writing_language: "en",
  status: "active",
  planned_novel_count: 9,
  novel_count: 4,
};

const mockSummary = {
  id: "series-1",
  title: "The Expanse",
  subtitle: null,
  status: "active",
  novel_count: 4,
};

const mockNovelSummary = {
  id: "novel-1",
  title: "Leviathan Wakes",
  author: "Author",
  genre: "sci-fi",
  writing_language: "en",
  is_demo: false,
  updated_at: "2026-07-30T00:00:00Z",
};

const mockPreview = {
  series_id: "series-1",
  novel_id: "novel-1",
  canon_empty: true,
  treatments: [
    {
      entry_id: "entry-1",
      slug: "magic",
      entity_type: "system",
      current_scope: "novel",
      target_scope: "series",
      reason: "Entity type 'system' defaults to Canon",
    },
  ],
};

const mockJoinResult = {
  series_id: "series-1",
  novel_id: "novel-1",
  position: 2,
  promoted_to_canon: 1,
  kept_as_overlay: 2,
};

const mockSettings = {
  series_id: "series-1",
  author_voice: null,
};

describe("seriesApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  // --- CRUD ----------------------------------------------------------------

  it("list → GET /series", async () => {
    let capturedMethod = "";
    server.use(
      http.get("*/api/v1/series", ({ request }) => {
        capturedMethod = request.method;
        return HttpResponse.json([mockSummary]);
      }),
    );

    const result = await seriesApi.list();

    expect(capturedMethod).toBe("GET");
    expect(result).toEqual([mockSummary]);
    expect(result[0].title).toBe("The Expanse");
  });

  it("get → GET /series/{id}", async () => {
    let capturedUrl = "";
    server.use(
      http.get("*/api/v1/series/series-1", ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json(mockSeries);
      }),
    );

    const result = await seriesApi.get("series-1");

    expect(capturedUrl).toContain("/api/v1/series/series-1");
    expect(result.id).toBe("series-1");
    expect(result.status).toBe("active");
  });

  it("create → POST /series with body", async () => {
    let capturedMethod = "";
    let capturedBody = "";
    server.use(
      http.post("*/api/v1/series", async ({ request }) => {
        capturedMethod = request.method;
        capturedBody = (await request.text()) as string;
        return HttpResponse.json(mockSeries);
      }),
    );

    const result = await seriesApi.create({
      title: "The Expanse",
      genre: "sci-fi",
    });

    expect(capturedMethod).toBe("POST");
    expect(JSON.parse(capturedBody)).toEqual({ title: "The Expanse", genre: "sci-fi" });
    expect(result.id).toBe("series-1");
  });

  it("update → PATCH /series/{id} with body", async () => {
    let capturedMethod = "";
    let capturedBody = "";
    server.use(
      http.patch("*/api/v1/series/series-1", async ({ request }) => {
        capturedMethod = request.method;
        capturedBody = (await request.text()) as string;
        return HttpResponse.json({ ...mockSeries, title: "Renamed" });
      }),
    );

    const result = await seriesApi.update("series-1", { title: "Renamed" });

    expect(capturedMethod).toBe("PATCH");
    expect(JSON.parse(capturedBody)).toEqual({ title: "Renamed" });
    expect(result.title).toBe("Renamed");
  });

  it("delete → DELETE /series/{id} → 204 void", async () => {
    let capturedMethod = "";
    server.use(
      http.delete("*/api/v1/series/series-1", ({ request }) => {
        capturedMethod = request.method;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const result = await seriesApi.delete("series-1");

    expect(capturedMethod).toBe("DELETE");
    expect(result).toBeUndefined();
  });

  // --- Novels in series ----------------------------------------------------

  it("listNovels → GET /series/{id}/novels", async () => {
    server.use(
      http.get("*/api/v1/series/series-1/novels", () => HttpResponse.json([mockNovelSummary])),
    );

    const result = await seriesApi.listNovels("series-1");

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("novel-1");
  });

  it("previewJoin → POST /series/{id}/novels with novel_id", async () => {
    let capturedMethod = "";
    let capturedBody = "";
    server.use(
      http.post("*/api/v1/series/series-1/novels", async ({ request }) => {
        capturedMethod = request.method;
        capturedBody = (await request.text()) as string;
        return HttpResponse.json(mockPreview);
      }),
    );

    const result = await seriesApi.previewJoin("series-1", "novel-1");

    expect(capturedMethod).toBe("POST");
    expect(JSON.parse(capturedBody)).toEqual({ novel_id: "novel-1" });
    expect(result.canon_empty).toBe(true);
    expect(result.treatments).toHaveLength(1);
  });

  it("applyJoin → POST /series/{id}/novels/{novelId}/apply with position", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedBody = "";
    server.use(
      http.post("*/api/v1/series/series-1/novels/novel-1/apply", async ({ request }) => {
        capturedUrl = request.url;
        capturedMethod = request.method;
        capturedBody = (await request.text()) as string;
        return HttpResponse.json(mockJoinResult);
      }),
    );

    const result = await seriesApi.applyJoin("series-1", "novel-1", 2);

    expect(capturedUrl).toContain("/api/v1/series/series-1/novels/novel-1/apply");
    expect(capturedMethod).toBe("POST");
    expect(JSON.parse(capturedBody)).toEqual({ position: 2 });
    expect(result.position).toBe(2);
    expect(result.promoted_to_canon).toBe(1);
  });

  it("removeNovel → DELETE /series/{id}/novels/{novelId} → 204 void", async () => {
    let capturedMethod = "";
    server.use(
      http.delete("*/api/v1/series/series-1/novels/novel-1", ({ request }) => {
        capturedMethod = request.method;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const result = await seriesApi.removeNovel("series-1", "novel-1");

    expect(capturedMethod).toBe("DELETE");
    expect(result).toBeUndefined();
  });

  it("reorderNovels → PATCH /series/{id}/novels/reorder with novel_ids → 204", async () => {
    let capturedMethod = "";
    let capturedBody = "";
    server.use(
      http.patch("*/api/v1/series/series-1/novels/reorder", async ({ request }) => {
        capturedMethod = request.method;
        capturedBody = (await request.text()) as string;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const result = await seriesApi.reorderNovels("series-1", ["n2", "n1", "n3"]);

    expect(capturedMethod).toBe("PATCH");
    expect(JSON.parse(capturedBody)).toEqual({ novel_ids: ["n2", "n1", "n3"] });
    expect(result).toBeUndefined();
  });

  // --- Settings ------------------------------------------------------------

  it("getSettings → GET /series/{id}/settings", async () => {
    server.use(
      http.get("*/api/v1/series/series-1/settings", () => HttpResponse.json(mockSettings)),
    );

    const result = await seriesApi.getSettings("series-1");

    expect(result.series_id).toBe("series-1");
    expect(result.author_voice).toBeNull();
  });

  it("updateSettings → PATCH /series/{id}/settings with body", async () => {
    let capturedMethod = "";
    let capturedBody = "";
    server.use(
      http.patch("*/api/v1/series/series-1/settings", async ({ request }) => {
        capturedMethod = request.method;
        capturedBody = (await request.text()) as string;
        return HttpResponse.json({ ...mockSettings, author_voice: { tone: "warm" } });
      }),
    );

    const result = await seriesApi.updateSettings("series-1", { author_voice: { tone: "warm" } });

    expect(capturedMethod).toBe("PATCH");
    expect(JSON.parse(capturedBody)).toEqual({ author_voice: { tone: "warm" } });
    expect(result.author_voice).toEqual({ tone: "warm" });
  });

  // --- Settings: context preview (C1 — Context-Window Slider) ---------------
  // Mirrors apps/api/narrare/series/series_history_preview_schemas.py
  // (SeriesHistoryPreviewResponse). model_context_window exercised as a
  // concrete number here; the nullable RULE-11 case lives in the type-parity
  // sample (types/__tests__/series.test.ts).

  it("getSettingsContextPreview → GET /series/{id}/settings/context-preview", async () => {
    const mockContextPreview = {
      series_id: "series-1",
      current_window_size: 3,
      effective_series_history_budget: 8192,
      effective_context_total: 32768,
      effective_tier_base: 24576,
      model_context_window: 32768,
      budget_source: "model_registry",
      previews: [
        {
          window_size: 1,
          token_budget: 8192,
          estimated_tokens: 4200,
          bands_total: 4,
          bands_full: 1,
          bands_short: 0,
          bands_truncated: 0,
          bands_dropped: 3,
          bands_missing: 0,
          budget_clipped: false,
        },
        {
          window_size: 3,
          token_budget: 8192,
          estimated_tokens: 8192,
          bands_total: 4,
          bands_full: 3,
          bands_short: 0,
          bands_truncated: 1,
          bands_dropped: 0,
          bands_missing: 0,
          budget_clipped: true,
        },
      ],
    };
    let capturedUrl = "";
    let capturedMethod = "";
    server.use(
      http.get("*/api/v1/series/series-1/settings/context-preview", ({ request }) => {
        capturedUrl = request.url;
        capturedMethod = request.method;
        return HttpResponse.json(mockContextPreview);
      }),
    );

    const result = await seriesApi.getSettingsContextPreview("series-1");

    expect(capturedUrl).toContain("/api/v1/series/series-1/settings/context-preview");
    expect(capturedMethod).toBe("GET");
    expect(result.series_id).toBe("series-1");
    expect(result.current_window_size).toBe(3);
    expect(result.model_context_window).toBe(32768);
    expect(result.previews).toHaveLength(2);
    expect(result.previews[1]).toEqual(mockContextPreview.previews[1]);
  });

  // --- KB scope toggle -----------------------------------------------------
  // Mirrors apps/api/narrare/kb/router_scope.py. The demote body carries ONLY
  // series_id — the target novel comes from the request PATH (the path novel_id
  // IS the overlay target, mirroring promote), so no target id rides in the body
  // (RULE-17 wire parity with KBDemoteRequest).

  const mockOverlayEntry = {
    scope: "novel",
    id: "entry-1",
    novel_id: "novel-1",
    series_id: "series-1",
    base_entry_id: null,
    entity_type: "character",
    name: "Anna",
    slug: "anna",
    status: "draft",
    body: null,
    metadata_: null,
    tags: null,
    template_version: null,
    source: "manual",
    review_status: "approved",
    embeddings_dirty: false,
    last_referenced_at: null,
    usage_count: 0,
    created_at: null,
    updated_at: null,
  };

  it("demoteToOverlay → POST /novels/{novelId}/kb/{entryId}/demote with series_id only", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedBody = "";
    server.use(
      http.post("*/api/v1/novels/novel-1/kb/entry-1/demote", async ({ request }) => {
        capturedUrl = request.url;
        capturedMethod = request.method;
        capturedBody = (await request.text()) as string;
        return HttpResponse.json(mockOverlayEntry);
      }),
    );

    const result = await seriesApi.demoteToOverlay("novel-1", "entry-1", "series-1");

    // The routing novel_id (and overlay target) is in the PATH, not the body.
    expect(capturedUrl).toContain("/api/v1/novels/novel-1/kb/entry-1/demote");
    expect(capturedMethod).toBe("POST");
    expect(JSON.parse(capturedBody)).toEqual({ series_id: "series-1" });
    expect(result.scope).toBe("novel");
    expect(result.novel_id).toBe("novel-1");
  });

  // --- Error propagation ---------------------------------------------------

  it("throws on a non-2xx error response", async () => {
    server.use(
      http.get("*/api/v1/series/series-1", () =>
        HttpResponse.json({ detail: "Series not found" }, { status: 404 }),
      ),
    );

    await expect(seriesApi.get("series-1")).rejects.toThrow("Series not found");
  });
});
