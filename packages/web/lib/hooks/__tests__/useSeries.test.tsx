/**
 * useSeries hook tests — TanStack Query hooks for Series CRUD.
 *
 * Covers: useSeriesList (read), useSeries (detail, disabled when no id),
 * useCreateSeries / useUpdateSeries / useDeleteSeries (mutations + cache
 * invalidation). Mirrors the useSummary/useKB test conventions:
 *   - vi.mock("@/lib/api/series") hoisted, mock helpers cast from the import.
 *   - createWrapper() supplies a retry:false QueryClient.
 *   - Invalidation is verified via a real spy on queryClient.invalidateQueries
 *     (asserts on actual cache-invalidation behavior, not mock internals).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/series", () => ({
  seriesApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

import { seriesApi } from "@/lib/api/series";
import {
  useCreateSeries,
  useDeleteSeries,
  useSeries,
  useSeriesList,
  useUpdateSeries,
} from "@/lib/hooks/useSeries";

const mockList = seriesApi.list as ReturnType<typeof vi.fn>;
const mockGet = seriesApi.get as ReturnType<typeof vi.fn>;
const mockCreate = seriesApi.create as ReturnType<typeof vi.fn>;
const mockUpdate = seriesApi.update as ReturnType<typeof vi.fn>;
const mockDelete = seriesApi.delete as ReturnType<typeof vi.fn>;

const summaryFixture = {
  id: "series-1",
  title: "The Expanse",
  subtitle: null,
  status: "active" as const,
  novel_count: 4,
};

const detailFixture = {
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

describe("useSeriesList", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("fetches the series list from seriesApi.list", async () => {
    mockList.mockResolvedValueOnce([summaryFixture]);

    const { result } = renderHook(() => useSeriesList(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockList).toHaveBeenCalledTimes(1);
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].title).toBe("The Expanse");
  });
});

describe("useSeries", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("fetches a single series by id", async () => {
    mockGet.mockResolvedValueOnce(detailFixture);

    const { result } = renderHook(() => useSeries("series-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith("series-1");
    expect(result.current.data?.title).toBe("The Expanse");
  });

  it("does not fetch when id is empty", async () => {
    const { result } = renderHook(() => useSeries(""), { wrapper: createWrapper() });

    // Let a microtask pass so a disabled query would have had a chance to run.
    await Promise.resolve();
    expect(mockGet).not.toHaveBeenCalled();
    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("useCreateSeries", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.create with the body and invalidates the list", async () => {
    const body = { title: "New Series" };
    mockCreate.mockResolvedValueOnce(detailFixture);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useCreateSeries(), { wrapper: createWrapper(queryClient) });

    result.current.mutate(body);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockCreate).toHaveBeenCalledWith(body);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["series"] });
  });
});

describe("useUpdateSeries", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.update and invalidates detail + list", async () => {
    const body = { title: "Renamed" };
    mockUpdate.mockResolvedValueOnce({ ...detailFixture, title: "Renamed" });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdateSeries("series-1"), {
      wrapper: createWrapper(queryClient),
    });

    result.current.mutate(body);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockUpdate).toHaveBeenCalledWith("series-1", body);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["series", "series-1"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["series"] });
  });
});

describe("useDeleteSeries", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("calls seriesApi.delete with the id and invalidates the list", async () => {
    mockDelete.mockResolvedValueOnce(undefined);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useDeleteSeries(), { wrapper: createWrapper(queryClient) });

    result.current.mutate("series-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockDelete).toHaveBeenCalledWith("series-1");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["series"] });
  });
});
