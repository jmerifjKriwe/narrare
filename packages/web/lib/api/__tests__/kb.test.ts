/**
 * KB API client tests — Knowledge Base CRUD, search, relationships, templates.
 *
 * Tests cover all exported functions from kbApi:
 * - Templates: getTemplate, listTemplates
 * - Entries: listEntries, getEntry, createEntry, updateEntry, deleteEntry, searchEntries
 * - Relationships: listRelationships, createRelationship, deleteRelationship, getInverseSuggestion
 * - References: resolveReferences, autocompleteEntries
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import { kbApi } from "../kb";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockEntry = {
  id: "entry-1",
  novel_id: "novel-1",
  entity_type: "character",
  name: "Anna Schmidt",
  slug: "anna-schmidt",
  status: "canon",
  tags: ["protagonist"],
  metadata: { role: "hero" },
  body: "A brave archivist.",
  template_version: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-05-27T00:00:00Z",
};

const mockEntryList = {
  items: [mockEntry],
  total: 1,
  page: 1,
  page_size: 20,
};

const mockTemplate = {
  entity_type: "character",
  scope: "global",
  content: "---\nprompt_type: kb\n---\n\n# Character Template\n{{content}}",
  base_content: null,
  schema_version: "2.0.0",
  based_on_version: null,
  is_overridden: false,
};

const mockTemplateInfo = [
  {
    entity_type: "character",
    scope: "global",
    schema_version: "1.0",
    has_override: false,
    has_update: false,
  },
];

const mockRelationship = {
  id: "rel-1",
  source_id: "entry-1",
  target_id: "entry-2",
  rel_type: "resides_in",
  label: "lives in",
  direction: "directed",
  metadata: {},
  source_name: "Anna",
  target_name: "Berlin",
  source_type: "character",
  target_type: "location",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-05-27T00:00:00Z",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("kbApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  // -- Templates --

  describe("getTemplate", () => {
    it("should GET /novels/:novelId/kb/templates/:entityType", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/templates/character", async () =>
          HttpResponse.json(mockTemplate),
        ),
      );

      const result = await kbApi.getTemplate("novel-1", "character");
      expect(result.entity_type).toBe("character");
      expect(result.is_overridden).toBe(false);
    });
  });

  describe("listTemplates", () => {
    it("should GET /novels/:novelId/kb/templates and return array", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/templates", async () =>
          HttpResponse.json(mockTemplateInfo),
        ),
      );

      const result = await kbApi.listTemplates("novel-1");
      expect(result).toHaveLength(1);
      expect(result[0].entity_type).toBe("character");
    });
  });

  // -- Entries --

  describe("listEntries", () => {
    it("should GET /novels/:novelId/kb/entries without params", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/entries", async () =>
          HttpResponse.json(mockEntryList),
        ),
      );

      const result = await kbApi.listEntries("novel-1");
      expect(result.items).toHaveLength(1);
      expect(result.total).toBe(1);
    });

    it("should include entity_type and tags as query params", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/novels/novel-1/kb/entries", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json(mockEntryList);
        }),
      );

      await kbApi.listEntries("novel-1", {
        entity_type: "character",
        tags: "protagonist",
        page: 2,
        page_size: 10,
      });

      const url = new URL(capturedUrl);
      expect(url.searchParams.get("entity_type")).toBe("character");
      expect(url.searchParams.get("tags")).toBe("protagonist");
      expect(url.searchParams.get("page")).toBe("2");
      expect(url.searchParams.get("page_size")).toBe("10");
    });
  });

  describe("getEntry", () => {
    it("should GET /novels/:novelId/kb/entries/:entryId", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/entries/entry-1", async () =>
          HttpResponse.json(mockEntry),
        ),
      );

      const result = await kbApi.getEntry("novel-1", "entry-1");
      expect(result.id).toBe("entry-1");
      expect(result.name).toBe("Anna Schmidt");
    });
  });

  describe("createEntry", () => {
    it("should POST to /novels/:novelId/kb/entries with body", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/entries", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockEntry);
        }),
      );

      const result = await kbApi.createEntry("novel-1", {
        entity_type: "character",
        name: "Anna Schmidt",
      });

      expect(capturedBody.entity_type).toBe("character");
      expect(capturedBody.name).toBe("Anna Schmidt");
      expect(result.id).toBe("entry-1");
    });
  });

  describe("updateEntry", () => {
    it("should PATCH /novels/:novelId/kb/entries/:entryId with body", async () => {
      let capturedMethod = "";
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.patch("*/api/v1/novels/novel-1/kb/entries/entry-1", async ({ request }) => {
          capturedMethod = request.method;
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...mockEntry, name: "Updated" });
        }),
      );

      const result = await kbApi.updateEntry("novel-1", "entry-1", { name: "Updated" });

      expect(capturedMethod).toBe("PATCH");
      expect(capturedBody.name).toBe("Updated");
      expect(result.name).toBe("Updated");
    });
  });

  describe("deleteEntry", () => {
    it("should DELETE /novels/:novelId/kb/entries/:entryId", async () => {
      let capturedMethod = "";

      server.use(
        http.delete("*/api/v1/novels/novel-1/kb/entries/entry-1", ({ request }) => {
          capturedMethod = request.method;
          return new HttpResponse(null, { status: 204 });
        }),
      );

      await kbApi.deleteEntry("novel-1", "entry-1");
      expect(capturedMethod).toBe("DELETE");
    });
  });

  describe("searchEntries", () => {
    it("should GET /novels/:novelId/kb/entries/search with q param", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/novels/novel-1/kb/entries/search", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json(mockEntryList);
        }),
      );

      const result = await kbApi.searchEntries("novel-1", { q: "Anna" });

      const url = new URL(capturedUrl);
      expect(url.searchParams.get("q")).toBe("Anna");
      expect(result.items).toHaveLength(1);
    });

    it("should include optional filter params in search URL", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/novels/novel-1/kb/entries/search", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json(mockEntryList);
        }),
      );

      await kbApi.searchEntries("novel-1", {
        q: "Anna",
        entity_type: "character",
        page: 1,
      });

      const url = new URL(capturedUrl);
      expect(url.searchParams.get("entity_type")).toBe("character");
    });
  });

  // -- Relationships --

  describe("listRelationships", () => {
    it("should GET /novels/:novelId/kb/entries/:entryId/relationships", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/entries/entry-1/relationships", async () =>
          HttpResponse.json([mockRelationship]),
        ),
      );

      const result = await kbApi.listRelationships("novel-1", "entry-1");
      expect(result).toHaveLength(1);
      expect(result[0].rel_type).toBe("resides_in");
    });

    it("should include direction as query param when provided", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/novels/novel-1/kb/entries/entry-1/relationships", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json([]);
        }),
      );

      await kbApi.listRelationships("novel-1", "entry-1", "outgoing");

      const url = new URL(capturedUrl);
      expect(url.searchParams.get("direction")).toBe("outgoing");
    });
  });

  describe("createRelationship", () => {
    it("should POST to /novels/:novelId/kb/relationships with body", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/relationships", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockRelationship);
        }),
      );

      const result = await kbApi.createRelationship("novel-1", {
        source_id: "entry-1",
        target_id: "entry-2",
        rel_type: "resides_in",
      });

      expect(capturedBody.source_id).toBe("entry-1");
      expect(capturedBody.rel_type).toBe("resides_in");
      expect(result.id).toBe("rel-1");
    });
  });

  describe("deleteRelationship", () => {
    it("should DELETE /novels/:novelId/kb/relationships/:relId", async () => {
      let capturedMethod = "";

      server.use(
        http.delete("*/api/v1/novels/novel-1/kb/relationships/rel-1", ({ request }) => {
          capturedMethod = request.method;
          return new HttpResponse(null, { status: 204 });
        }),
      );

      await kbApi.deleteRelationship("novel-1", "rel-1");
      expect(capturedMethod).toBe("DELETE");
    });
  });

  describe("getInverseSuggestion", () => {
    it("should GET /novels/:novelId/kb/relationships/inverse-suggestion with rel_type", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/relationships/inverse-suggestion", async () =>
          HttpResponse.json({
            rel_type: "resides_in",
            inverse_rel_type: "resident_of",
            description: "The inverse relationship.",
          }),
        ),
      );

      const result = await kbApi.getInverseSuggestion("novel-1", "resides_in");
      expect(result.inverse_rel_type).toBe("resident_of");
    });

    it("should URL-encode the rel_type parameter", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/novels/novel-1/kb/relationships/inverse-suggestion", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json({
            rel_type: "father of",
            inverse_rel_type: "child of",
            description: "",
          });
        }),
      );

      await kbApi.getInverseSuggestion("novel-1", "father of");

      const url = new URL(capturedUrl);
      expect(url.searchParams.get("rel_type")).toBe("father of");
    });
  });

  // -- References --

  describe("resolveReferences", () => {
    it("should POST to /novels/:novelId/kb/resolve-references with text", async () => {
      let capturedBody: Record<string, unknown> = {};

      server.use(
        http.post("*/api/v1/novels/novel-1/kb/resolve-references", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({
            resolved: [
              {
                mention: "@Anna",
                entry_id: "entry-1",
                entry_name: "Anna",
                entity_type: "character",
                slug: "anna",
              },
            ],
            html: '<span class="mention">@Anna</span>',
          });
        }),
      );

      const result = await kbApi.resolveReferences("novel-1", "@Anna went home.");

      expect(capturedBody.text).toBe("@Anna went home.");
      expect(result.resolved).toHaveLength(1);
      expect(result.html).toBeTruthy();
    });
  });

  describe("autocompleteEntries", () => {
    it("should GET /novels/:novelId/kb/entries/autocomplete with q param", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/novels/novel-1/kb/entries/autocomplete", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json([
            { id: "entry-1", name: "Anna Schmidt", entity_type: "character", slug: "anna-schmidt" },
          ]);
        }),
      );

      const result = await kbApi.autocompleteEntries("novel-1", "Ann");

      const url = new URL(capturedUrl);
      expect(url.searchParams.get("q")).toBe("Ann");
      expect(url.searchParams.get("limit")).toBe("10");
      expect(result).toHaveLength(1);
    });

    it("should URL-encode query parameter", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/novels/novel-1/kb/entries/autocomplete", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json([]);
        }),
      );

      await kbApi.autocompleteEntries("novel-1", "Anna & Bob");

      const url = new URL(capturedUrl);
      expect(url.searchParams.get("q")).toBe("Anna & Bob");
    });
  });
});
