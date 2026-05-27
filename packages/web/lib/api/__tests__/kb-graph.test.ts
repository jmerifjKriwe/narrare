/**
 * KB Graph API client tests — graph visualization endpoints.
 *
 * Tests:
 * 1. kbGraphApi.getGraph GETs correct URL with optional filters
 * 2. kbGraphApi.getGraph returns GraphResponse
 * 3. kbGraphApi.getShortestPath GETs correct URL
 * 4. kbGraphApi.getShortestPath returns ShortestPathResponse
 * 5. Error handling
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "../client";
import { kbGraphApi } from "../kb-graph";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockGraphResponse = {
  nodes: [
    {
      id: "node-1",
      label: "Anna Schmidt",
      entity_type: "character",
      status: "canon",
      tags: ["protagonist"],
      metadata: { role: "hero" },
      degree: 3,
    },
    {
      id: "node-2",
      label: "Berlin",
      entity_type: "location",
      status: "canon",
      tags: null,
      metadata: null,
      degree: 2,
    },
  ],
  edges: [
    {
      id: "edge-1",
      source: "node-1",
      target: "node-2",
      label: "lives in",
      rel_type: "resides_in",
      direction: "directed",
      weight: 1.0,
    },
  ],
  stats: {
    node_count: 2,
    edge_count: 1,
    isolated_count: 0,
    connected_components: 1,
    entity_type_counts: { character: 1, location: 1 },
    rel_type_counts: { resides_in: 1 },
  },
};

const mockPathResponse = {
  path: ["node-1", "node-2"],
  length: 1,
  entity_names: ["Anna Schmidt", "Berlin"],
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("kbGraphApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  describe("getGraph", () => {
    it("should GET /novels/:novelId/kb/graph and return GraphResponse", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/graph", async () =>
          HttpResponse.json(mockGraphResponse),
        ),
      );

      const result = await kbGraphApi.getGraph("novel-1");

      expect(result.nodes).toHaveLength(2);
      expect(result.edges).toHaveLength(1);
      expect(result.stats.node_count).toBe(2);
    });

    it("should include entity_types filter as query param", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/novels/novel-1/kb/graph", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json(mockGraphResponse);
        }),
      );

      await kbGraphApi.getGraph("novel-1", { entity_types: ["character", "location"] });

      const url = new URL(capturedUrl);
      expect(url.searchParams.get("entity_types")).toBe("character,location");
    });

    it("should include rel_types filter as query param", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/novels/novel-1/kb/graph", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json(mockGraphResponse);
        }),
      );

      await kbGraphApi.getGraph("novel-1", { rel_types: ["resides_in"] });

      const url = new URL(capturedUrl);
      expect(url.searchParams.get("rel_types")).toBe("resides_in");
    });

    it("should include max_nodes and max_edges as query params", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/novels/novel-1/kb/graph", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json(mockGraphResponse);
        }),
      );

      await kbGraphApi.getGraph("novel-1", { max_nodes: 50, max_edges: 100 });

      const url = new URL(capturedUrl);
      expect(url.searchParams.get("max_nodes")).toBe("50");
      expect(url.searchParams.get("max_edges")).toBe("100");
    });

    it("should not include query params when no filter provided", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/novels/novel-1/kb/graph", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json(mockGraphResponse);
        }),
      );

      await kbGraphApi.getGraph("novel-1");

      const url = new URL(capturedUrl);
      expect(url.search).toBe("");
    });

    it("should return nodes with correct structure", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/graph", async () =>
          HttpResponse.json(mockGraphResponse),
        ),
      );

      const result = await kbGraphApi.getGraph("novel-1");

      const node = result.nodes[0];
      expect(node.id).toBe("node-1");
      expect(node.label).toBe("Anna Schmidt");
      expect(node.entity_type).toBe("character");
      expect(node.degree).toBe(3);
    });

    it("should return edges with correct structure", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/graph", async () =>
          HttpResponse.json(mockGraphResponse),
        ),
      );

      const result = await kbGraphApi.getGraph("novel-1");

      const edge = result.edges[0];
      expect(edge.source).toBe("node-1");
      expect(edge.target).toBe("node-2");
      expect(edge.rel_type).toBe("resides_in");
    });

    it("should handle empty graph", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/graph", async () =>
          HttpResponse.json({
            nodes: [],
            edges: [],
            stats: {
              node_count: 0,
              edge_count: 0,
              isolated_count: 0,
              connected_components: 0,
              entity_type_counts: {},
              rel_type_counts: {},
            },
          }),
        ),
      );

      const result = await kbGraphApi.getGraph("novel-1");
      expect(result.nodes).toHaveLength(0);
      expect(result.stats.node_count).toBe(0);
    });

    it("should handle 500 error", async () => {
      server.use(
        http.get("*/api/v1/novels/:novelId/kb/graph", async () =>
          HttpResponse.json({ detail: "Server error" }, { status: 500 }),
        ),
      );

      await expect(kbGraphApi.getGraph("novel-1")).rejects.toThrow();
    });
  });

  describe("getShortestPath", () => {
    it("should GET /novels/:novelId/kb/graph/shortest-path with source and target", async () => {
      let capturedUrl = "";

      server.use(
        http.get("*/api/v1/novels/novel-1/kb/graph/shortest-path", ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json(mockPathResponse);
        }),
      );

      const result = await kbGraphApi.getShortestPath("novel-1", "node-1", "node-2");

      const url = new URL(capturedUrl);
      expect(url.searchParams.get("source_id")).toBe("node-1");
      expect(url.searchParams.get("target_id")).toBe("node-2");
      expect(result.path).toEqual(["node-1", "node-2"]);
      expect(result.length).toBe(1);
      expect(result.entity_names).toEqual(["Anna Schmidt", "Berlin"]);
    });

    it("should return null path when no path exists", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/graph/shortest-path", async () =>
          HttpResponse.json({ path: null, length: null, entity_names: null }),
        ),
      );

      const result = await kbGraphApi.getShortestPath("novel-1", "node-1", "node-99");
      expect(result.path).toBeNull();
      expect(result.length).toBeNull();
    });

    it("should handle 404 error", async () => {
      server.use(
        http.get("*/api/v1/novels/novel-1/kb/graph/shortest-path", async () =>
          HttpResponse.json({ detail: "Entity not found" }, { status: 404 }),
        ),
      );

      await expect(kbGraphApi.getShortestPath("novel-1", "missing", "node-2")).rejects.toThrow();
    });
  });
});
