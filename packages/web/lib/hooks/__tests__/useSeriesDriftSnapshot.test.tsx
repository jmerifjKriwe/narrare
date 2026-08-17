/**
 * Tests for the C2 drift-snapshot hook + run-mutation invalidation.
 *
 * Self-contained QueryClient wrapper (mirrors the useBandSummary test
 * pattern): the API client is module-mocked; the REAL seriesKeys module
 * provides the expected key, so the invalidation assertion does not
 * restate the key shape.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getDriftSnapshot: vi.fn(),
  checkSeriesConsistency: vi.fn(),
  checkSeriesVoiceDrift: vi.fn(),
}));

vi.mock("@/lib/api/series", () => ({
  seriesApi: api,
}));

import { seriesKeys } from "@/lib/hooks/seriesKeys";
import {
  useSeriesConsistency,
  useSeriesDriftSnapshot,
  useSeriesVoiceDrift,
} from "@/lib/hooks/useSeriesDrift";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { wrapper: Wrapper, queryClient };
}

const EMPTY_SNAPSHOT = {
  series_id: "s1",
  novel_id: "n1",
  generated_at: null,
  stale: false,
  consistency: null,
  voice_drift: null,
};

describe("useSeriesDriftSnapshot", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("is disabled until both ids are set", () => {
    api.getDriftSnapshot.mockResolvedValue(EMPTY_SNAPSHOT);
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useSeriesDriftSnapshot("s1", ""), {
      wrapper,
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(api.getDriftSnapshot).not.toHaveBeenCalled();
  });

  it("fetches the snapshot when enabled", async () => {
    api.getDriftSnapshot.mockResolvedValue({ ...EMPTY_SNAPSHOT, stale: true });
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useSeriesDriftSnapshot("s1", "n1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.data?.stale).toBe(true));
    expect(api.getDriftSnapshot).toHaveBeenCalledWith("s1", "n1");
  });
});

describe("run mutations invalidate the snapshot (C2)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useSeriesConsistency invalidates driftSnapshot on success", async () => {
    api.checkSeriesConsistency.mockResolvedValue({ conflicts: [] });
    const { wrapper, queryClient } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useSeriesConsistency("s1"), { wrapper });

    await act(async () => {
      await result.current.mutateAsync("n1");
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: seriesKeys.driftSnapshot("s1", "n1"),
    });
  });

  it("useSeriesVoiceDrift invalidates driftSnapshot on success", async () => {
    api.checkSeriesVoiceDrift.mockResolvedValue({ result: null, no_profile: null });
    const { wrapper, queryClient } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useSeriesVoiceDrift("s1"), { wrapper });

    await act(async () => {
      await result.current.mutateAsync("n1");
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: seriesKeys.driftSnapshot("s1", "n1"),
    });
  });
});
