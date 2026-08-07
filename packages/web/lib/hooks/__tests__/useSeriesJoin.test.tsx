/**
 * useSeriesJoin hook tests — Join flow (preview-then-apply) mutations.
 *
 * useJoinPreview: POST /series/{id}/novels → JoinPreview (does NOT mutate).
 * useApplyJoin:   POST /series/{id}/novels/{novelId}/apply → JoinResult,
 *                 invalidates the series detail + list AND the novels list on
 *                 success (joining flips the novel's server-side series_id, so
 *                 the ["novels"] query must refetch or the joined novel lingers
 *                 as a standalone ghost card / dropdown entry).
 *
 * Invalidation is verified with a real queryClient.invalidateQueries spy.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/series", () => ({
  seriesApi: {
    previewJoin: vi.fn(),
    applyJoin: vi.fn(),
  },
}));

import { seriesApi } from "@/lib/api/series";
import { novelsKeys } from "@/lib/hooks/novelsKeys";
import { useApplyJoin, useJoinPreview } from "@/lib/hooks/useSeriesJoin";

const mockPreviewJoin = seriesApi.previewJoin as ReturnType<typeof vi.fn>;
const mockApplyJoin = seriesApi.applyJoin as ReturnType<typeof vi.fn>;

const joinPreviewFixture = {
  series_id: "series-1",
  novel_id: "novel-1",
  canon_empty: true,
  treatments: [
    {
      entry_id: "entry-1",
      slug: "magic-system",
      entity_type: "system",
      current_scope: "novel" as const,
      target_scope: "series" as const,
      reason: "Entity type 'system' defaults to Canon",
    },
  ],
};

const joinResultFixture = {
  series_id: "series-1",
  novel_id: "novel-1",
  position: 2,
  promoted_to_canon: 1,
  kept_as_overlay: 0,
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

describe("useJoinPreview", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.previewJoin with (seriesId, novelId) and returns the preview", async () => {
    mockPreviewJoin.mockResolvedValueOnce(joinPreviewFixture);

    const { result } = renderHook(() => useJoinPreview("series-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate("novel-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockPreviewJoin).toHaveBeenCalledWith("series-1", "novel-1");
    expect(result.current.data?.canon_empty).toBe(true);
    expect(result.current.data?.treatments).toHaveLength(1);
  });
});

describe("useApplyJoin", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.applyJoin and invalidates series detail + list + novels list", async () => {
    mockApplyJoin.mockResolvedValueOnce(joinResultFixture);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useApplyJoin("series-1"), {
      wrapper: createWrapper(queryClient),
    });

    result.current.mutate({ novelId: "novel-1", position: 2 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApplyJoin).toHaveBeenCalledWith("series-1", "novel-1", 2);
    expect(result.current.data?.position).toBe(2);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["series", "series-1"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["series"] });
    // Joining flips the novel's series_id server-side, so the novels list must
    // refetch — otherwise the joined novel lingers as a ghost standalone card.
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: novelsKeys.all });
  });
});
