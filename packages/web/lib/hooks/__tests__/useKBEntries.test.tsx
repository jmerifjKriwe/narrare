/**
 * useKB entry CRUD/count hook tests — complements useKB.test.tsx (templates).
 *
 * Covers: useKBEntries, useKBEntry, useKBSearch, useCreateKBEntry,
 * useUpdateKBEntry, useDeleteKBEntry, useKBEntryCount, useKBTotalCount.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/kb", () => ({
  kbApi: {
    listEntries: vi.fn(),
    getEntry: vi.fn(),
    createEntry: vi.fn(),
    updateEntry: vi.fn(),
    deleteEntry: vi.fn(),
    searchEntries: vi.fn(),
  },
}));

import { type KBEntry, type KBEntryListResponse, kbApi } from "@/lib/api/kb";
import {
  useCreateKBEntry,
  useDeleteKBEntry,
  useKBEntries,
  useKBEntry,
  useKBEntryCount,
  useKBSearch,
  useKBTotalCount,
  useUpdateKBEntry,
} from "@/lib/hooks/useKB";

const listEntries = vi.mocked(kbApi.listEntries);
const getEntry = vi.mocked(kbApi.getEntry);
const createEntry = vi.mocked(kbApi.createEntry);
const updateEntry = vi.mocked(kbApi.updateEntry);
const deleteEntry = vi.mocked(kbApi.deleteEntry);
const searchEntries = vi.mocked(kbApi.searchEntries);

const entryFixture: KBEntry = {
  id: "e1",
  novel_id: "novel-1",
  entity_type: "character",
  name: "Anna",
  slug: "anna",
  status: "canon",
  tags: [],
  metadata: {},
  body: "",
  template_version: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const listFixture: KBEntryListResponse = {
  items: [entryFixture],
  total: 1,
  page: 1,
  page_size: 20,
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

describe("useKBEntries", () => {
  it("fetches paginated entries", async () => {
    listEntries.mockResolvedValueOnce(listFixture);

    const { result } = renderHook(() => useKBEntries("novel-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(listEntries).toHaveBeenCalledWith("novel-1", undefined);
    expect(result.current.data?.total).toBe(1);
  });

  it("is disabled when novelId is empty", () => {
    const { result } = renderHook(() => useKBEntries(""), { wrapper: createWrapper() });

    expect(result.current.fetchStatus).toBe("idle");
    expect(listEntries).not.toHaveBeenCalled();
  });
});

describe("useKBEntry", () => {
  it("fetches a single entry by id", async () => {
    getEntry.mockResolvedValueOnce(entryFixture);

    const { result } = renderHook(() => useKBEntry("novel-1", "e1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getEntry).toHaveBeenCalledWith("novel-1", "e1");
    expect(result.current.data?.name).toBe("Anna");
  });

  it("is disabled when entryId is null", () => {
    const { result } = renderHook(() => useKBEntry("novel-1", null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(getEntry).not.toHaveBeenCalled();
  });
});

describe("useKBSearch", () => {
  it("searches entries when query is non-empty", async () => {
    searchEntries.mockResolvedValueOnce(listFixture);

    const { result } = renderHook(() => useKBSearch("novel-1", "ann"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(searchEntries).toHaveBeenCalledWith("novel-1", { q: "ann" });
  });

  it("is disabled when query is empty", () => {
    const { result } = renderHook(() => useKBSearch("novel-1", ""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(searchEntries).not.toHaveBeenCalled();
  });
});

describe("useCreateKBEntry", () => {
  it("creates an entry and invalidates the entries list", async () => {
    createEntry.mockResolvedValueOnce(entryFixture);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useCreateKBEntry("novel-1"), {
      wrapper: createWrapper(),
    });

    const data = { entity_type: "character" as const, name: "Anna" };
    result.current.mutate(data);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(createEntry).toHaveBeenCalledWith("novel-1", data);
    expect(invalidateSpy).toHaveBeenCalled();
    invalidateSpy.mockRestore();
  });
});

describe("useUpdateKBEntry", () => {
  it("updates an entry and invalidates list + single entry caches", async () => {
    updateEntry.mockResolvedValueOnce(entryFixture);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useUpdateKBEntry("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ entryId: "e1", data: { name: "Anna B" } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(updateEntry).toHaveBeenCalledWith("novel-1", "e1", { name: "Anna B" });
    expect(invalidateSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
    invalidateSpy.mockRestore();
  });
});

describe("useDeleteKBEntry", () => {
  it("deletes an entry and invalidates the entries list", async () => {
    deleteEntry.mockResolvedValueOnce(undefined);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useDeleteKBEntry("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate("e1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(deleteEntry).toHaveBeenCalledWith("novel-1", "e1");
    expect(invalidateSpy).toHaveBeenCalled();
    invalidateSpy.mockRestore();
  });
});

describe("useKBEntryCount", () => {
  it("returns the total count for an entity type", async () => {
    listEntries.mockResolvedValueOnce({ ...listFixture, total: 7 });

    const { result } = renderHook(() => useKBEntryCount("novel-1", "character"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current).toBe(7));
    expect(listEntries).toHaveBeenCalledWith("novel-1", { entity_type: "character", page_size: 1 });
  });

  it("returns 0 when data is not yet available", async () => {
    const { result } = renderHook(() => useKBEntryCount(""), { wrapper: createWrapper() });

    // Disabled query → no data → count is 0.
    expect(result.current).toBe(0);
  });
});

describe("useKBTotalCount", () => {
  it("returns the total count across all types", async () => {
    listEntries.mockResolvedValueOnce({ ...listFixture, total: 42 });

    const { result } = renderHook(() => useKBTotalCount("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current).toBe(42));
  });

  it("returns 0 when data is not yet available", () => {
    const { result } = renderHook(() => useKBTotalCount(""), { wrapper: createWrapper() });

    expect(result.current).toBe(0);
  });
});
