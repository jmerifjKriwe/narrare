/**
 * useBandSummary hooks tests (Spec 2, Task 8).
 *
 * Verifies the four TanStack Query hooks wrap the correct `seriesApi` methods
 * and that the three mutations invalidate the band-summary query cache on
 * success (so the card re-fetches after regenerate / override / clear) plus
 * the C1 settings-preview query (which derives from summaries).
 *
 * Pattern mirrors `useSummary.test.tsx`: `seriesApi` is mocked per-module, a
 * QueryClientProvider wrapper isolates cache state, and `invalidateQueries`
 * is spied to assert the cache-busting behaviour.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BandSummary } from "@/types";

const { mockGet, mockGenerate, mockUpdateOverride, mockClearOverride } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockGenerate: vi.fn(),
  mockUpdateOverride: vi.fn(),
  mockClearOverride: vi.fn(),
}));

vi.mock("@/lib/api/series", () => ({
  seriesApi: {
    getBandSummary: (...args: unknown[]) => mockGet(...args),
    generateBandSummary: (...args: unknown[]) => mockGenerate(...args),
    updateBandSummaryOverride: (...args: unknown[]) => mockUpdateOverride(...args),
    clearBandSummaryOverride: (...args: unknown[]) => mockClearOverride(...args),
  },
}));

import { seriesKeys } from "@/lib/hooks/seriesKeys";
import {
  useBandSummary,
  useClearBandSummaryOverride,
  useGenerateBandSummary,
  useUpdateBandSummaryOverride,
} from "@/lib/hooks/useBandSummary";

const SERIES_ID = "series-1";
const NOVEL_ID = "novel-1";

const fixture: BandSummary = {
  novel_id: NOVEL_ID,
  full_summary: "Full text…",
  short_summary: "Short.",
  override: null,
  generated_at: "2026-08-02T12:00:00Z",
};

function makeClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
}

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("useBandSummary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
  });

  it("fetches the band summary via seriesApi.getBandSummary", async () => {
    mockGet.mockResolvedValueOnce(fixture);
    const client = makeClient();

    const { result } = renderHook(() => useBandSummary(SERIES_ID, NOVEL_ID), {
      wrapper: wrapper(client),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(mockGet).toHaveBeenCalledWith(SERIES_ID, NOVEL_ID);
    expect(result.current.data).toEqual(fixture);
  });

  it("is disabled when seriesId is empty", () => {
    mockGet.mockResolvedValueOnce(fixture);
    const client = makeClient();

    renderHook(() => useBandSummary("", NOVEL_ID), { wrapper: wrapper(client) });
    expect(mockGet).not.toHaveBeenCalled();
  });
});

describe("useGenerateBandSummary", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.generateBandSummary and invalidates the cache on success", async () => {
    mockGenerate.mockResolvedValueOnce(fixture);
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useGenerateBandSummary(SERIES_ID, NOVEL_ID), {
      wrapper: wrapper(client),
    });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(mockGenerate).toHaveBeenCalledWith(SERIES_ID, NOVEL_ID);
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: seriesKeys.bandSummary(SERIES_ID, NOVEL_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: seriesKeys.settingsPreview(SERIES_ID),
    });
  });
});

describe("useUpdateBandSummaryOverride", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.updateBandSummaryOverride and invalidates the cache", async () => {
    const updated: BandSummary = { ...fixture, override: "Manual" };
    mockUpdateOverride.mockResolvedValueOnce(updated);
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateBandSummaryOverride(SERIES_ID, NOVEL_ID), {
      wrapper: wrapper(client),
    });

    result.current.mutate("Manual");

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(mockUpdateOverride).toHaveBeenCalledWith(SERIES_ID, NOVEL_ID, "Manual");
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: seriesKeys.bandSummary(SERIES_ID, NOVEL_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: seriesKeys.settingsPreview(SERIES_ID),
    });
  });
});

describe("useClearBandSummaryOverride", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.clearBandSummaryOverride and invalidates the cache", async () => {
    mockClearOverride.mockResolvedValueOnce(undefined);
    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useClearBandSummaryOverride(SERIES_ID, NOVEL_ID), {
      wrapper: wrapper(client),
    });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(mockClearOverride).toHaveBeenCalledWith(SERIES_ID, NOVEL_ID);
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: seriesKeys.bandSummary(SERIES_ID, NOVEL_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: seriesKeys.settingsPreview(SERIES_ID),
    });
  });
});
