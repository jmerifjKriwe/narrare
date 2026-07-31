/**
 * useCanonKB hook tests — Series-Canon KB CRUD (Task 5.2).
 *
 * Mirrors the novel-scoped useKB hooks but targets /series/{seriesId}/kb.
 * Covers: useCanonKB (list read + disabled-when-empty), useCreateCanonEntry,
 * useUpdateCanonEntry, useDeleteCanonEntry (mutations + cache invalidation).
 *
 * Invalidation is verified with a real queryClient.invalidateQueries spy,
 * matching the useSeries / useKB test conventions.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/series", () => ({
  seriesApi: {
    listCanonKB: vi.fn(),
    createCanonEntry: vi.fn(),
    updateCanonEntry: vi.fn(),
    deleteCanonEntry: vi.fn(),
  },
}));

import { seriesApi } from "@/lib/api/series";
import {
  useCanonKB,
  useCreateCanonEntry,
  useDeleteCanonEntry,
  useUpdateCanonEntry,
} from "@/lib/hooks/useCanonKB";

const mockList = seriesApi.listCanonKB as ReturnType<typeof vi.fn>;
const mockCreate = seriesApi.createCanonEntry as ReturnType<typeof vi.fn>;
const mockUpdate = seriesApi.updateCanonEntry as ReturnType<typeof vi.fn>;
const mockDelete = seriesApi.deleteCanonEntry as ReturnType<typeof vi.fn>;

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
  body: "Protagonist",
  metadata_: null,
  tags: ["hero"],
  template_version: null,
  source: "manual",
  review_status: "approved",
  embeddings_dirty: false,
  last_referenced_at: null,
  usage_count: 0,
  created_at: "2026-07-29T00:00:00Z",
  updated_at: "2026-07-29T00:00:00Z",
};

function createWrapper(client?: QueryClient) {
  const queryClient =
    client ??
    new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
        mutations: { retry: false },
      },
    });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useCanonKB", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("fetches the canon KB list for a series", async () => {
    mockList.mockResolvedValueOnce([canonEntryFixture]);

    const { result } = renderHook(() => useCanonKB("series-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockList).toHaveBeenCalledWith("series-1");
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].name).toBe("Anna");
  });

  it("is disabled when seriesId is empty", async () => {
    const { result } = renderHook(() => useCanonKB(""), { wrapper: createWrapper() });

    await Promise.resolve();
    expect(mockList).not.toHaveBeenCalled();
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("handles API errors", async () => {
    mockList.mockRejectedValueOnce(new Error("Server error"));

    const { result } = renderHook(() => useCanonKB("series-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Server error");
  });
});

describe("useCreateCanonEntry", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.createCanonEntry and invalidates the canon list", async () => {
    const body = { entity_type: "character", name: "Bruno" };
    mockCreate.mockResolvedValueOnce({ ...canonEntryFixture, id: "entry-2", name: "Bruno" });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useCreateCanonEntry("series-1"), {
      wrapper: createWrapper(queryClient),
    });

    result.current.mutate(body);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockCreate).toHaveBeenCalledWith("series-1", body);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["series", "series-1", "kb"] });
  });
});

describe("useUpdateCanonEntry", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.updateCanonEntry and invalidates the canon list + detail", async () => {
    const body = { name: "Anna Renamed" };
    mockUpdate.mockResolvedValueOnce({ ...canonEntryFixture, name: "Anna Renamed" });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdateCanonEntry("series-1", "entry-1"), {
      wrapper: createWrapper(queryClient),
    });

    result.current.mutate(body);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockUpdate).toHaveBeenCalledWith("series-1", "entry-1", body);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["series", "series-1", "kb"] });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["series", "series-1", "kb", "entry-1"],
    });
  });
});

describe("useDeleteCanonEntry", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.deleteCanonEntry and invalidates the canon list", async () => {
    mockDelete.mockResolvedValueOnce(undefined);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useDeleteCanonEntry("series-1"), {
      wrapper: createWrapper(queryClient),
    });

    result.current.mutate("entry-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockDelete).toHaveBeenCalledWith("series-1", "entry-1");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["series", "series-1", "kb"] });
  });
});
