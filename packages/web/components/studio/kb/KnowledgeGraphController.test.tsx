/**
 * useKnowledgeGraphController tests — graph orchestration hook.
 *
 * Verifies the controller wires its sub-hooks together: graph data is fetched
 * (MSW), the entity-type filter memoizes into filteredData/elements, and the
 * zoom/search/layout handlers delegate to the Cytoscape ref returned by
 * useGraphCytoscape. The leaf cytoscape sub-hooks are mocked so the
 * controller's own orchestration logic (state, memoization, handler→cy
 * wiring) is what we exercise — the cytoscape rendering layer is a separate
 * concern exercised elsewhere.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { Core as CytoscapeCore } from "cytoscape";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { useKnowledgeGraphController } from "./KnowledgeGraphController";

// ---------------------------------------------------------------------------
// Mocks — leaf sub-hooks so the controller's orchestration is the SUT.
// ---------------------------------------------------------------------------

const graphResponse = {
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

// A controllable fake Cytoscape core. Each method chains where the real API
// chains (elements().removeClass(...)) so the controller handlers run.
function makeFakeCy(): CytoscapeCore {
  const elements = vi.fn(() => ({ removeClass: vi.fn() }));
  return {
    elements,
    layout: vi.fn(() => ({ run: vi.fn() })),
    getElementById: vi.fn((id: string) => ({ length: id ? 1 : 0, addClass: vi.fn() })),
    animate: vi.fn(),
    // zoom(): no-arg read returns 1; with-arg write returns undefined.
    zoom: vi.fn((factor?: number) => (typeof factor === "number" ? undefined : 1)),
    center: vi.fn(),
    fit: vi.fn(),
    destroy: vi.fn(),
  } as unknown as CytoscapeCore;
}

const fakeCy = makeFakeCy();
const cyRef = { current: fakeCy };

const shortestPathState = {
  pathSourceId: null as string | null,
  setPathSourceId: vi.fn(),
  pathResult: null,
  pathMutation: { mutate: vi.fn() },
  handleClosePathPanel: vi.fn(),
};

vi.mock("./useGraphCytoscape", () => ({
  CLEAR_CLASSES: "selected highlighted dimmed path-node path-edge",
  useGraphCytoscape: () => ({ cyRef, stylesheet: {} }),
}));

vi.mock("./useGraphShortestPath", () => ({
  useGraphShortestPath: () => shortestPathState,
}));

// ---------------------------------------------------------------------------
// Wrapper + helpers
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  // A stable container ref so useGraphCytoscape's (mocked) consumer gets a node.
  const containerRef = { current: document.createElement("div") };
  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return { wrapper: Wrapper, containerRef };
}

function renderController(novelId = "novel-1") {
  const { wrapper, containerRef } = makeWrapper();
  const onSelectEntry = vi.fn();
  const result = renderHook(
    () => useKnowledgeGraphController({ novelId, onSelectEntry, containerRef }),
    { wrapper },
  );
  return { ...result, onSelectEntry };
}

function graphHandler() {
  return http.get("*/api/v1/novels/novel-1/kb/graph", async () => HttpResponse.json(graphResponse));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useKnowledgeGraphController", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.resetHandlers();
    server.use(graphHandler());
    shortestPathState.pathSourceId = null;
    shortestPathState.pathResult = null;
  });

  it("initializes with default state", () => {
    const { result } = renderController();

    expect(result.current.layout).toBe("cose");
    expect(result.current.entityTypeFilter).toEqual(new Set());
    expect(result.current.searchQuery).toBe("");
    expect(result.current.selectedNodeId).toBeNull();
    // cyRef is forwarded from the mocked sub-hook.
    expect(result.current.cyRef).toBe(cyRef);
  });

  it("fetches graph data and derives elements from it", async () => {
    const { result } = renderController();

    // Initially loading with no data.
    expect(result.current.isLoading).toBe(true);

    await waitFor(() => expect(result.current.graphData?.nodes).toBeDefined());

    expect(result.current.graphData?.nodes).toHaveLength(2);
    // filteredData mirrors graphData when no filter is set.
    expect(result.current.filteredData).toEqual(result.current.graphData);
  });

  it("filters data by entity type and recomputes elements", async () => {
    const { result } = renderController();

    await waitFor(() => expect(result.current.graphData?.nodes).toBeDefined());
    // Sanity: full graph first.
    expect(result.current.filteredData?.nodes).toHaveLength(2);

    act(() => {
      result.current.setEntityTypeFilter(new Set(["character"]));
    });

    // Only the character node survives; its edge has no location peer so it drops.
    expect(result.current.filteredData?.nodes).toHaveLength(1);
    expect(result.current.filteredData?.nodes[0].id).toBe("node-1");
    expect(result.current.filteredData?.edges).toHaveLength(0);
  });

  it("handleSearchClear resets the query and clears search-match classes", async () => {
    const { result } = renderController();

    await waitFor(() => expect(result.current.graphData?.nodes).toBeDefined());
    act(() => {
      result.current.setSearchQuery("anna");
    });
    expect(result.current.searchQuery).toBe("anna");

    act(() => {
      result.current.handleSearchClear();
    });

    expect(result.current.searchQuery).toBe("");
    expect(fakeCy.elements).toHaveBeenCalled();
  });

  it("handleZoomIn / handleZoomOut delegate to the cy ref", async () => {
    const { result } = renderController();

    await waitFor(() => expect(result.current.graphData?.nodes).toBeDefined());

    act(() => result.current.handleZoomIn());
    // handleZoomIn reads zoom() then writes zoom() — two calls.
    expect(fakeCy.zoom).toHaveBeenCalledTimes(2);
    expect(fakeCy.center).toHaveBeenCalledTimes(1);

    act(() => result.current.handleZoomOut());
    // handleZoomOut likewise reads then writes (2 more) + center (1 more).
    expect(fakeCy.zoom).toHaveBeenCalledTimes(4);
    expect(fakeCy.center).toHaveBeenCalledTimes(2);
  });

  it("handleFit delegates to cy.fit", async () => {
    const { result } = renderController();

    await waitFor(() => expect(result.current.graphData?.nodes).toBeDefined());

    act(() => result.current.handleFit());
    expect(fakeCy.fit).toHaveBeenCalledWith(undefined, 30);
  });

  it("handleLayoutChange updates layout and runs the new cy layout", async () => {
    const { result } = renderController();

    await waitFor(() => expect(result.current.graphData?.nodes).toBeDefined());

    act(() => result.current.handleLayoutChange("concentric"));

    expect(result.current.layout).toBe("concentric");
    expect(fakeCy.layout).toHaveBeenCalledTimes(1);
  });

  it("handleSearchSubmit is a no-op without a query (edge case)", async () => {
    const { result } = renderController();

    await waitFor(() => expect(result.current.graphData?.nodes).toBeDefined());

    const animateBefore = (fakeCy.animate as ReturnType<typeof vi.fn>).mock.calls.length;
    act(() => result.current.handleSearchSubmit());
    expect((fakeCy.animate as ReturnType<typeof vi.fn>).mock.calls.length).toBe(animateBefore);
  });

  it("handleSearchSubmit animates to the first matching node", async () => {
    const { result } = renderController();

    await waitFor(() => expect(result.current.graphData?.nodes).toBeDefined());
    act(() => {
      result.current.setSearchQuery("anna");
    });

    act(() => result.current.handleSearchSubmit());

    // searchNodes("anna") matches "Anna Schmidt"; cy.getElementById + animate fire.
    expect(fakeCy.getElementById).toHaveBeenCalledWith("node-1");
    expect(fakeCy.animate).toHaveBeenCalledTimes(1);
  });

  it("handleSearchSubmit does nothing when no node matches", async () => {
    const { result } = renderController();

    await waitFor(() => expect(result.current.graphData?.nodes).toBeDefined());
    act(() => {
      result.current.setSearchQuery("zzznomatch");
    });

    const animateBefore = (fakeCy.animate as ReturnType<typeof vi.fn>).mock.calls.length;
    act(() => result.current.handleSearchSubmit());
    expect((fakeCy.animate as ReturnType<typeof vi.fn>).mock.calls.length).toBe(animateBefore);
  });

  it("forwards the shortest-path controls from its sub-hook", () => {
    const { result } = renderController();
    expect(result.current.pathSourceId).toBeNull();
    expect(result.current.pathResult).toBeNull();
    expect(typeof result.current.handleClosePathPanel).toBe("function");
  });
});
