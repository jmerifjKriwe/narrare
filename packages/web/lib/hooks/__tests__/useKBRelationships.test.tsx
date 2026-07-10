/**
 * useKBRelationships hook tests — TanStack Query hooks for KB relationships.
 *
 * Tests:
 * 1. useKBRelationships fetches relationships when entryId is set
 * 2. useKBRelationships is disabled when entryId is null
 * 3. useCreateKBRelationship calls API and invalidates relationships
 * 4. useDeleteKBRelationship calls API and invalidates relationships
 * 5. both mutations propagate API errors
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/kb", () => ({
  kbApi: {
    listRelationships: vi.fn(),
    createRelationship: vi.fn(),
    deleteRelationship: vi.fn(),
  },
}));

import { type KBRelationship, kbApi } from "@/lib/api/kb";
import {
  useCreateKBRelationship,
  useDeleteKBRelationship,
  useKBRelationships,
} from "@/lib/hooks/useKBRelationships";

const listRelationships = vi.mocked(kbApi.listRelationships);
const createRelationship = vi.mocked(kbApi.createRelationship);
const deleteRelationship = vi.mocked(kbApi.deleteRelationship);

const relFixture: KBRelationship = {
  id: "rel-1",
  source_id: "char-1",
  target_id: "char-2",
  rel_type: "ally",
  label: "allies",
  direction: "directed",
  metadata: {},
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
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

describe("useKBRelationships", () => {
  it("fetches relationships for a given entry", async () => {
    listRelationships.mockResolvedValueOnce([relFixture]);

    const { result } = renderHook(() => useKBRelationships("novel-1", "char-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(listRelationships).toHaveBeenCalledWith("novel-1", "char-1");
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].rel_type).toBe("ally");
  });

  it("is disabled when entryId is null", () => {
    const { result } = renderHook(() => useKBRelationships("novel-1", null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(listRelationships).not.toHaveBeenCalled();
  });
});

describe("useCreateKBRelationship", () => {
  it("creates a relationship and invalidates the relationships cache", async () => {
    createRelationship.mockResolvedValueOnce(relFixture);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useCreateKBRelationship("novel-1", "char-1"), {
      wrapper: createWrapper(),
    });

    const payload = { source_id: "char-1", target_id: "char-2", rel_type: "ally" };
    result.current.mutate(payload);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(createRelationship).toHaveBeenCalledWith("novel-1", payload);
    expect(invalidateSpy).toHaveBeenCalled();
    invalidateSpy.mockRestore();
  });

  it("propagates API errors", async () => {
    createRelationship.mockRejectedValueOnce(new Error("Create failed"));

    const { result } = renderHook(() => useCreateKBRelationship("novel-1", "char-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ source_id: "char-1", target_id: "char-2", rel_type: "ally" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Create failed");
  });
});

describe("useDeleteKBRelationship", () => {
  it("deletes a relationship and invalidates the relationships cache", async () => {
    deleteRelationship.mockResolvedValueOnce(undefined);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useDeleteKBRelationship("novel-1", "char-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate("rel-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(deleteRelationship).toHaveBeenCalledWith("novel-1", "rel-1");
    expect(invalidateSpy).toHaveBeenCalled();
    invalidateSpy.mockRestore();
  });

  it("propagates API errors", async () => {
    deleteRelationship.mockRejectedValueOnce(new Error("Delete failed"));

    const { result } = renderHook(() => useDeleteKBRelationship("novel-1", "char-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate("rel-1");

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Delete failed");
  });
});
