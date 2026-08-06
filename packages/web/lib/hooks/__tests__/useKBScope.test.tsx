/**
 * useKBScope hook tests — KB scope-toggle mutations (promote/demote).
 *
 * Series Foundation Spec 1, Slice 5 (Task 5.1).
 *
 * usePromoteToCanon: POST /novels/{novelId}/kb/{entryId}/promote → SeriesKBEntry.
 *   On success invalidates the novel-scoped KB entries cache AND the series
 *   Canon-KB cache (series_id taken from the response).
 * useDemoteToOverlay: POST /novels/{novelId}/kb/{entryId}/demote with body
 *   {series_id} → NovelKBEntry (the path novel is the overlay target). On
 *   success invalidates the Canon-KB cache AND the target novel's KB entries
 *   (novel_id from response).
 *
 * Invalidation is verified with a real queryClient.invalidateQueries spy
 * (asserts on actual cache-invalidation behavior, not mock internals). Mirrors
 * the useSeries / useSeriesJoin test conventions.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/series", () => ({
  seriesApi: {
    promoteToCanon: vi.fn(),
    demoteToOverlay: vi.fn(),
  },
}));

import { seriesApi } from "@/lib/api/series";
import { useDemoteToOverlay, usePromoteToCanon } from "@/lib/hooks/useKBScope";

const mockPromote = seriesApi.promoteToCanon as ReturnType<typeof vi.fn>;
const mockDemote = seriesApi.demoteToOverlay as ReturnType<typeof vi.fn>;

// Promote returns a Series-Canon entry (scope=series, series_id set).
const canonEntryFixture = {
  scope: "series" as const,
  id: "entry-1",
  series_id: "series-1",
  novel_id: null,
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

// Demote returns a Novel-Overlay entry (scope=novel, novel_id = target).
const overlayEntryFixture = {
  scope: "novel" as const,
  id: "entry-1",
  novel_id: "novel-2",
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

function createWrapper(client?: QueryClient) {
  const queryClient =
    client ??
    new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("usePromoteToCanon", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.promoteToCanon with (novelId, entryId) and returns the canon entry", async () => {
    mockPromote.mockResolvedValueOnce(canonEntryFixture);

    const { result } = renderHook(() => usePromoteToCanon("novel-1", "entry-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockPromote).toHaveBeenCalledWith("novel-1", "entry-1");
    expect(result.current.data?.scope).toBe("series");
    expect(result.current.data?.series_id).toBe("series-1");
  });

  it("invalidates the novel KB entries cache and the series Canon-KB cache", async () => {
    mockPromote.mockResolvedValueOnce(canonEntryFixture);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => usePromoteToCanon("novel-1", "entry-1"), {
      wrapper: createWrapper(queryClient),
    });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Overlay left this novel's KB entries.
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["kb", "novel-1", "entries"],
    });
    // Canon list for the series (series_id taken from the response).
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["series", "series-1", "kb"],
    });
  });
});

describe("useDemoteToOverlay", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.demoteToOverlay with the routing novel, entry, and series", async () => {
    mockDemote.mockResolvedValueOnce(overlayEntryFixture);

    const { result } = renderHook(() => useDemoteToOverlay("series-1", "entry-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ novelId: "novel-1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockDemote).toHaveBeenCalledWith("novel-1", "entry-1", "series-1");
    expect(result.current.data?.scope).toBe("novel");
    expect(result.current.data?.novel_id).toBe("novel-2");
  });

  it("invalidates the Canon-KB cache and the target novel's KB entries cache", async () => {
    mockDemote.mockResolvedValueOnce(overlayEntryFixture);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useDemoteToOverlay("series-1", "entry-1"), {
      wrapper: createWrapper(queryClient),
    });

    result.current.mutate({ novelId: "novel-1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Canon list lost an entry (seriesId captured at hook construction).
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["series", "series-1", "kb"],
    });
    // Overlay landed in the target novel's KB (novel_id taken from response).
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["kb", "novel-2", "entries"],
    });
  });
});
