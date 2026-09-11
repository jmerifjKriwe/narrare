/**
 * Notes API client tests — covers all `notesApi` methods.
 *
 * Pattern: MSW request interception (see lib/api/__tests__/series.test.ts),
 * NOT global.fetch mutation. Verifies HTTP method, path, query string,
 * request body, and return shape for every endpoint shipped in NOTES-001 §5:
 *   - CRUD: list, get, create, update, delete
 *   - Tags autocomplete: tags (with/without prefix)
 *   - Search: search (semantic with lexical fallback, mode badge)
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import { notesApi } from "../notes";

// ---------------------------------------------------------------------------
// Fixtures (mirror apps/api/narrare/notes/schemas.py shapes)
// ---------------------------------------------------------------------------

const mockNote = {
  id: "note-1",
  title: "Lighthouse motif",
  content: "The lighthouse appears in every chapter finale.",
  note_type: "idea",
  tags: ["motif", "symbolism"],
  novel_id: null,
  series_id: null,
  created_at: "2026-08-20T10:00:00Z",
  updated_at: "2026-08-21T12:00:00Z",
};

const mockTags = { tags: ["motif", "symbolism", "plot"] };

const mockSearchResponse = {
  mode: "semantic",
  query: "lighthouse",
  results: [{ ...mockNote, similarity: 0.92 }],
};

describe("notesApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  // --- CRUD ----------------------------------------------------------------

  it("list → GET /notes without query string when no params", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    server.use(
      http.get("*/api/v1/notes", ({ request }) => {
        capturedUrl = request.url;
        capturedMethod = request.method;
        return HttpResponse.json([mockNote]);
      }),
    );

    const result = await notesApi.list();

    expect(capturedMethod).toBe("GET");
    expect(capturedUrl).not.toContain("?");
    expect(result).toEqual([mockNote]);
    expect(result[0].note_type).toBe("idea");
  });

  it("list → GET /notes with all filters serialized as query params", async () => {
    let capturedUrl = "";
    server.use(
      http.get("*/api/v1/notes", ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json([]);
      }),
    );

    await notesApi.list({
      note_type: "question",
      tag: "lighthouse",
      novel_id: "novel-1",
      series_id: "series-1",
      q: "keeper",
      limit: 25,
      offset: 50,
    });

    const params = new URL(capturedUrl).searchParams;
    expect(params.get("note_type")).toBe("question");
    expect(params.get("tag")).toBe("lighthouse");
    expect(params.get("novel_id")).toBe("novel-1");
    expect(params.get("series_id")).toBe("series-1");
    expect(params.get("q")).toBe("keeper");
    expect(params.get("limit")).toBe("25");
    expect(params.get("offset")).toBe("50");
  });

  it("get → GET /notes/{id}", async () => {
    let capturedUrl = "";
    server.use(
      http.get("*/api/v1/notes/note-1", ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json(mockNote);
      }),
    );

    const result = await notesApi.get("note-1");

    expect(capturedUrl).toContain("/api/v1/notes/note-1");
    expect(result.id).toBe("note-1");
    expect(result.title).toBe("Lighthouse motif");
  });

  it("create → POST /notes with body", async () => {
    let capturedMethod = "";
    let capturedBody = "";
    server.use(
      http.post("*/api/v1/notes", async ({ request }) => {
        capturedMethod = request.method;
        capturedBody = (await request.text()) as string;
        return HttpResponse.json(mockNote, { status: 201 });
      }),
    );

    const result = await notesApi.create({
      title: "Lighthouse motif",
      content: "The lighthouse appears in every chapter finale.",
      note_type: "idea",
      tags: ["motif", "symbolism"],
    });

    expect(capturedMethod).toBe("POST");
    expect(JSON.parse(capturedBody)).toEqual({
      title: "Lighthouse motif",
      content: "The lighthouse appears in every chapter finale.",
      note_type: "idea",
      tags: ["motif", "symbolism"],
    });
    expect(result.id).toBe("note-1");
  });

  it("update → PATCH /notes/{id} with body incl. explicit null", async () => {
    let capturedMethod = "";
    let capturedBody = "";
    server.use(
      http.patch("*/api/v1/notes/note-1", async ({ request }) => {
        capturedMethod = request.method;
        capturedBody = (await request.text()) as string;
        return HttpResponse.json({ ...mockNote, title: null });
      }),
    );

    const result = await notesApi.update("note-1", { title: null });

    expect(capturedMethod).toBe("PATCH");
    expect(JSON.parse(capturedBody)).toEqual({ title: null });
    expect(result.title).toBeNull();
  });

  it("delete → DELETE /notes/{id} → 204 void", async () => {
    let capturedMethod = "";
    server.use(
      http.delete("*/api/v1/notes/note-1", ({ request }) => {
        capturedMethod = request.method;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const result = await notesApi.delete("note-1");

    expect(capturedMethod).toBe("DELETE");
    expect(result).toBeUndefined();
  });

  // --- Tags autocomplete -----------------------------------------------------

  it("tags → GET /notes/tags without query when no prefix", async () => {
    let capturedUrl = "";
    server.use(
      http.get("*/api/v1/notes/tags", ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json(mockTags);
      }),
    );

    const result = await notesApi.tags();

    expect(capturedUrl).toContain("/api/v1/notes/tags");
    expect(capturedUrl).not.toContain("?");
    expect(result.tags).toEqual(["motif", "symbolism", "plot"]);
  });

  it("tags → GET /notes/tags?q=… with encoded prefix", async () => {
    let capturedUrl = "";
    server.use(
      http.get("*/api/v1/notes/tags", ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({ tags: ["plot twist"] });
      }),
    );

    await notesApi.tags("plot ");

    const params = new URL(capturedUrl).searchParams;
    expect(params.get("q")).toBe("plot ");
    expect(capturedUrl).toContain("q=plot%20");
  });

  // --- Search ---------------------------------------------------------------

  it("search → POST /notes/search with body, returns mode badge + hits", async () => {
    let capturedMethod = "";
    let capturedBody = "";
    server.use(
      http.post("*/api/v1/notes/search", async ({ request }) => {
        capturedMethod = request.method;
        capturedBody = (await request.text()) as string;
        return HttpResponse.json(mockSearchResponse);
      }),
    );

    const result = await notesApi.search({
      query: "lighthouse",
      note_type: "idea",
      limit: 10,
    });

    expect(capturedMethod).toBe("POST");
    expect(JSON.parse(capturedBody)).toEqual({
      query: "lighthouse",
      note_type: "idea",
      limit: 10,
    });
    expect(result.mode).toBe("semantic");
    expect(result.query).toBe("lighthouse");
    expect(result.results).toHaveLength(1);
    expect(result.results[0].similarity).toBe(0.92);
  });

  it("search → lexical fallback mode flows through unchanged", async () => {
    server.use(
      http.post("*/api/v1/notes/search", () =>
        HttpResponse.json({ mode: "lexical", query: "x", results: [] }),
      ),
    );

    const result = await notesApi.search({ query: "x" });

    expect(result.mode).toBe("lexical");
    expect(result.results).toEqual([]);
  });

  // --- Error propagation ---------------------------------------------------

  it("throws on a non-2xx error response", async () => {
    server.use(
      http.get("*/api/v1/notes/note-1", () =>
        HttpResponse.json({ detail: "Note not found" }, { status: 404 }),
      ),
    );

    await expect(notesApi.get("note-1")).rejects.toThrow("Note not found");
  });
});
