/**
 * useNovelSeries hook tests — resolves the Series a novel belongs to.
 *
 * Orchestrates novelsApi.get (→ series_id) then seriesApi.get when set.
 * Returns null for standalone novels (series_id null) and stays idle when
 * novelId is undefined.
 *
 * NOTE: the backend NovelResponse schema does not yet expose `series_id`
 * (see apps/api/narrare/novels/schemas.py). The frontend Novel type carries
 * `series_id: string | null` to model the DB column / intended contract;
 * runtime correctness requires the backend to expose the field. These tests
 * mock the *intended* response shape.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/novels", () => ({
  novelsApi: { get: vi.fn() },
}));
vi.mock("@/lib/api/series", () => ({
  seriesApi: { get: vi.fn() },
}));

import { novelsApi } from "@/lib/api/novels";
import { seriesApi } from "@/lib/api/series";
import { useNovelSeries } from "@/lib/hooks/useNovelSeries";

const mockNovelGet = novelsApi.get as ReturnType<typeof vi.fn>;
const mockSeriesGet = seriesApi.get as ReturnType<typeof vi.fn>;

const seriesFixture = {
  id: "series-1",
  user_id: "user-1",
  title: "The Expanse",
  subtitle: null,
  description: null,
  genre: "sci-fi",
  writing_language: "en",
  status: "active" as const,
  planned_novel_count: 9,
  novel_count: 4,
};

function novelFixture(seriesId: string | null) {
  return {
    id: "novel-1",
    title: "Leviathan Wakes",
    author: "Author",
    genre: "sci-fi",
    writing_language: "en",
    tone: "",
    story_structure: "three_act",
    logline: "",
    synopsis: "",
    is_demo: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    series_id: seriesId,
  };
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useNovelSeries", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("returns null when the novel has no series", async () => {
    mockNovelGet.mockResolvedValueOnce(novelFixture(null));

    const { result } = renderHook(() => useNovelSeries("novel-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockNovelGet).toHaveBeenCalledWith("novel-1");
    expect(mockSeriesGet).not.toHaveBeenCalled();
    expect(result.current.data).toBeNull();
  });

  it("fetches and returns the Series when the novel belongs to one", async () => {
    mockNovelGet.mockResolvedValueOnce(novelFixture("series-1"));
    mockSeriesGet.mockResolvedValueOnce(seriesFixture);

    const { result } = renderHook(() => useNovelSeries("novel-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockNovelGet).toHaveBeenCalledWith("novel-1");
    expect(mockSeriesGet).toHaveBeenCalledWith("series-1");
    expect(result.current.data?.title).toBe("The Expanse");
  });

  it("does not run when novelId is undefined", async () => {
    const { result } = renderHook(() => useNovelSeries(undefined), { wrapper: createWrapper() });

    await Promise.resolve();
    expect(mockNovelGet).not.toHaveBeenCalled();
    expect(result.current.fetchStatus).toBe("idle");
  });
});
