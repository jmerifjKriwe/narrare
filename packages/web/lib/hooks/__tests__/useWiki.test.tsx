/**
 * useWiki hook tests — TanStack Query hooks for Wiki summaries.
 *
 * Tests: useWikiSummary, useWikiSummaries, useWikiChapterSummary, useWikiIndex,
 * useWikiRefresh, useWikiMarkStale — fetch, disabled states, invalidation.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/wiki", () => ({
  wikiApi: {
    getSummary: vi.fn(),
    getSummaries: vi.fn(),
    getChapterSummary: vi.fn(),
    getWikiIndex: vi.fn(),
    refreshSummary: vi.fn(),
    markStale: vi.fn(),
  },
}));

import {
  type WikiChapterSummaryResponse,
  type WikiIndexResponse,
  type WikiRefreshResponse,
  type WikiSummaryListResponse,
  type WikiSummaryResponse,
  wikiApi,
} from "@/lib/api/wiki";
import {
  useWikiChapterSummary,
  useWikiIndex,
  useWikiMarkStale,
  useWikiRefresh,
  useWikiSummaries,
  useWikiSummary,
} from "@/lib/hooks/useWiki";

const getSummary = vi.mocked(wikiApi.getSummary);
const getSummaries = vi.mocked(wikiApi.getSummaries);
const getChapterSummary = vi.mocked(wikiApi.getChapterSummary);
const getWikiIndex = vi.mocked(wikiApi.getWikiIndex);
const refreshSummary = vi.mocked(wikiApi.refreshSummary);
const markStale = vi.mocked(wikiApi.markStale);

const summaryFixture: WikiSummaryResponse = {
  id: "s1",
  novel_id: "novel-1",
  entity_id: "char-1",
  narrative_summary: "The protagonist.",
  role_in_story: "hero",
  key_attributes: ["brave"],
  relationships: null,
  chapter_references: null,
  character_arc: null,
  status: "fresh",
  version: 1,
  generated_at: "2026-01-01T00:00:00Z",
  refreshed_at: null,
};

const listFixture: WikiSummaryListResponse = { items: [summaryFixture], total: 1 };
const chapterFixture: WikiChapterSummaryResponse = {
  id: "cs1",
  chapter_id: "ch-1",
  narrative_summary: "Things happen.",
  key_events: ["event"],
  entities_involved: null,
  themes: null,
  emotional_arc: null,
  status: "fresh",
  version: 1,
  generated_at: null,
};
const indexFixture: WikiIndexResponse = {
  novel_id: "novel-1",
  total_summaries: 1,
  fresh_count: 1,
  stale_count: 0,
  pending_count: 0,
  last_generated_at: null,
};
const refreshFixture: WikiRefreshResponse = {
  summary_id: "s1",
  status: "fresh",
  message: "ok",
};

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

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("useWikiSummary", () => {
  it("fetches a single summary", async () => {
    getSummary.mockResolvedValueOnce(summaryFixture);

    const { result } = renderHook(() => useWikiSummary("novel-1", "char-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getSummary).toHaveBeenCalledWith("novel-1", "char-1");
    expect(result.current.data?.entity_id).toBe("char-1");
  });

  it("is disabled when entityId is empty", () => {
    const { result } = renderHook(() => useWikiSummary("novel-1", ""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(getSummary).not.toHaveBeenCalled();
  });
});

describe("useWikiSummaries", () => {
  it("fetches the summary list", async () => {
    getSummaries.mockResolvedValueOnce(listFixture);

    const { result } = renderHook(() => useWikiSummaries("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getSummaries).toHaveBeenCalledWith("novel-1", undefined);
    expect(result.current.data?.total).toBe(1);
  });

  it("is disabled when novelId is empty", () => {
    const { result } = renderHook(() => useWikiSummaries(""), { wrapper: createWrapper() });

    expect(result.current.fetchStatus).toBe("idle");
    expect(getSummaries).not.toHaveBeenCalled();
  });
});

describe("useWikiChapterSummary", () => {
  it("fetches a chapter summary", async () => {
    getChapterSummary.mockResolvedValueOnce(chapterFixture);

    const { result } = renderHook(() => useWikiChapterSummary("novel-1", "ch-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getChapterSummary).toHaveBeenCalledWith("novel-1", "ch-1");
    expect(result.current.data?.chapter_id).toBe("ch-1");
  });
});

describe("useWikiIndex", () => {
  it("fetches the wiki index", async () => {
    getWikiIndex.mockResolvedValueOnce(indexFixture);

    const { result } = renderHook(() => useWikiIndex("novel-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getWikiIndex).toHaveBeenCalledWith("novel-1");
    expect(result.current.data?.fresh_count).toBe(1);
  });
});

describe("useWikiRefresh", () => {
  it("refreshes a summary and invalidates caches", async () => {
    refreshSummary.mockResolvedValueOnce(refreshFixture);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useWikiRefresh("novel-1"), { wrapper: createWrapper() });

    result.current.mutate({ entityId: "char-1", force: true });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(refreshSummary).toHaveBeenCalledWith("novel-1", "char-1", true);
    expect(invalidateSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
    invalidateSpy.mockRestore();
  });
});

describe("useWikiMarkStale", () => {
  it("marks summaries stale and invalidates the wiki cache", async () => {
    markStale.mockResolvedValueOnce({ count: 3 });
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useWikiMarkStale("novel-1"), { wrapper: createWrapper() });

    result.current.mutate("v2");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(markStale).toHaveBeenCalledWith("novel-1", "v2");
    expect(result.current.data).toEqual({ count: 3 });
    expect(invalidateSpy).toHaveBeenCalled();
    invalidateSpy.mockRestore();
  });
});
