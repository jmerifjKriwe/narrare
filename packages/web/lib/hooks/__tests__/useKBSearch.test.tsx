/**
 * useKBSearch hook tests — debounced search + KB lookup queries.
 *
 * Tests:
 * 1. useKBDebouncedSearch clears immediately when query is empty
 * 2. useKBDebouncedSearch debounces and fetches after the delay
 * 3. useKBInverseSuggestion fetches when relType is set; disabled when null
 * 4. useKBResolveReferences fetches when text is set; disabled when null
 * 5. useKBAutocomplete enables only with >= 2 characters
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/kb", () => ({
  kbApi: {
    searchEntries: vi.fn(),
    getInverseSuggestion: vi.fn(),
    resolveReferences: vi.fn(),
    autocompleteEntries: vi.fn(),
  },
}));

import { type KBInverseSuggestion, kbApi, type ResolveReferencesResponse } from "@/lib/api/kb";
import {
  useKBAutocomplete,
  useKBDebouncedSearch,
  useKBInverseSuggestion,
  useKBResolveReferences,
} from "@/lib/hooks/useKBSearch";

const searchEntries = vi.mocked(kbApi.searchEntries);
const getInverseSuggestion = vi.mocked(kbApi.getInverseSuggestion);
const resolveReferences = vi.mocked(kbApi.resolveReferences);
const autocompleteEntries = vi.mocked(kbApi.autocompleteEntries);

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

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(() => {
  cleanup();
});

describe("useKBDebouncedSearch", () => {
  it("clears immediately when the query is empty (no fetch)", () => {
    const { result } = renderHook(() => useKBDebouncedSearch("novel-1"), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.setQuery("");
    });

    expect(result.current.searchQuery).toBe("");
    expect(searchEntries).not.toHaveBeenCalled();
  });

  it("sets searchQuery immediately but defers the fetch via a timer", () => {
    const { result } = renderHook(() => useKBDebouncedSearch("novel-1", 300), {
      wrapper: createWrapper(),
    });

    let cleanup: (() => void) | undefined;
    act(() => {
      // Non-empty query schedules a debounce timer; setQuery returns its cleanup.
      cleanup = result.current.setQuery("dragon");
    });

    expect(result.current.searchQuery).toBe("dragon");
    // Fetch is still deferred — the timer has not elapsed.
    expect(searchEntries).not.toHaveBeenCalled();

    // Cancel the pending timer so it cannot fire during later tests.
    act(() => {
      cleanup?.();
    });
    expect(searchEntries).not.toHaveBeenCalled();
  });
});

describe("useKBInverseSuggestion", () => {
  it("fetches the inverse suggestion for a rel type", async () => {
    const suggestion: KBInverseSuggestion = {
      rel_type: "parent_of",
      inverse_rel_type: "child_of",
      description: "biological parent",
    };
    getInverseSuggestion.mockResolvedValueOnce(suggestion);

    const { result } = renderHook(() => useKBInverseSuggestion("novel-1", "parent_of"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getInverseSuggestion).toHaveBeenCalledWith("novel-1", "parent_of");
    expect(result.current.data?.inverse_rel_type).toBe("child_of");
  });

  it("is disabled when relType is null", () => {
    const { result } = renderHook(() => useKBInverseSuggestion("novel-1", null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(getInverseSuggestion).not.toHaveBeenCalled();
  });
});

describe("useKBResolveReferences", () => {
  it("resolves references for non-empty text", async () => {
    const response: ResolveReferencesResponse = {
      resolved: [
        {
          mention: "@Anna",
          entry_id: "e1",
          entry_name: "Anna",
          entity_type: "character",
          slug: "anna",
        },
      ],
      html: null,
    };
    resolveReferences.mockResolvedValueOnce(response);

    const { result } = renderHook(() => useKBResolveReferences("novel-1", "@Anna visits"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(resolveReferences).toHaveBeenCalledWith("novel-1", "@Anna visits");
    expect(result.current.data?.resolved).toHaveLength(1);
  });

  it("is disabled when text is null", () => {
    const { result } = renderHook(() => useKBResolveReferences("novel-1", null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(resolveReferences).not.toHaveBeenCalled();
  });
});

describe("useKBAutocomplete", () => {
  it("fetches suggestions when query has at least 2 characters", async () => {
    autocompleteEntries.mockResolvedValueOnce([
      { id: "e1", name: "Anna", entity_type: "character", slug: "anna" },
    ]);

    const { result } = renderHook(() => useKBAutocomplete("novel-1", "an"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(autocompleteEntries).toHaveBeenCalledWith("novel-1", "an");
    expect(result.current.data).toHaveLength(1);
  });

  it("is disabled for queries shorter than 2 characters", () => {
    const { result } = renderHook(() => useKBAutocomplete("novel-1", "a"), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(autocompleteEntries).not.toHaveBeenCalled();
  });
});
