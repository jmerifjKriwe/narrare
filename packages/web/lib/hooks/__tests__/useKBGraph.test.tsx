/**
 * useKBGraph hook tests — TanStack Query hooks for KB graph visualization.
 *
 * Tests:
 * 1. useKBGraph fetches graph data via kbGraphApi.getGraph
 * 2. useKBGraph is disabled when novelId is empty
 * 3. useKBGraphPath mutation calls getShortestPath and invalidates cache
 * 4. useKBGraphPath handles errors
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client module
vi.mock("@/lib/api/kb-graph", () => ({
  kbGraphApi: {
    getGraph: vi.fn(),
    getShortestPath: vi.fn(),
  },
}));

import { kbGraphApi } from "@/lib/api/kb-graph";
import { useKBGraph, useKBGraphPath } from "@/lib/hooks/useKBGraph";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const mockGetGraph = kbGraphApi.getGraph as ReturnType<typeof vi.fn>;
const mockGetShortestPath = kbGraphApi.getShortestPath as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockGraphResponse = {
  nodes: [
    {
      id: "n-1",
      label: "Anna",
      entity_type: "character",
      status: "canon",
      tags: null,
      metadata: null,
      degree: 1,
    },
  ],
  edges: [],
  stats: {
    node_count: 1,
    edge_count: 0,
    isolated_count: 0,
    connected_components: 1,
    entity_type_counts: { character: 1 },
    rel_type_counts: {},
  },
};

const mockPathResponse = {
  path: ["n-1", "n-2"],
  length: 1,
  entity_names: ["Anna", "Berlin"],
};

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useKBGraph", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("fetches graph data via kbGraphApi.getGraph", async () => {
    mockGetGraph.mockResolvedValueOnce(mockGraphResponse);

    const { result } = renderHook(() => useKBGraph("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGetGraph).toHaveBeenCalledWith("novel-1", undefined);
    expect(result.current.data?.nodes).toHaveLength(1);
    expect(result.current.data?.stats.node_count).toBe(1);
  });

  it("passes entity types filter to getGraph", async () => {
    mockGetGraph.mockResolvedValueOnce(mockGraphResponse);

    renderHook(() => useKBGraph("novel-1", ["character"]), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(mockGetGraph).toHaveBeenCalledWith("novel-1", { entity_types: ["character"] });
    });
  });

  it("is disabled when novelId is empty", () => {
    const { result } = renderHook(() => useKBGraph(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetGraph).not.toHaveBeenCalled();
  });

  it("handles API errors", async () => {
    mockGetGraph.mockRejectedValueOnce(new Error("Graph fetch failed"));

    const { result } = renderHook(() => useKBGraph("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Graph fetch failed");
  });
});

describe("useKBGraphPath", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls kbGraphApi.getShortestPath with source and target", async () => {
    mockGetShortestPath.mockResolvedValueOnce(mockPathResponse);

    const { result } = renderHook(() => useKBGraphPath("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ sourceId: "n-1", targetId: "n-2" });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGetShortestPath).toHaveBeenCalledWith("novel-1", "n-1", "n-2");
    expect(result.current.data?.length).toBe(1);
  });

  it("invalidates kb-graph cache on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
        mutations: { retry: false },
      },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    mockGetShortestPath.mockResolvedValueOnce(mockPathResponse);

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useKBGraphPath("novel-1"), { wrapper });

    result.current.mutate({ sourceId: "n-1", targetId: "n-2" });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["kb-graph", "novel-1"],
    });
  });

  it("handles API errors", async () => {
    mockGetShortestPath.mockRejectedValueOnce(new Error("Path not found"));

    const { result } = renderHook(() => useKBGraphPath("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ sourceId: "n-1", targetId: "n-99" });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Path not found");
  });
});
