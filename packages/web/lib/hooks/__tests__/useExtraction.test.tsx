/**
 * useExtraction hook tests — TanStack Query hooks for KB extraction.
 *
 * Tests:
 * 1. useExtractChapter calls correct endpoint
 * 2. useExtractChapter handles API errors
 * 3. useApplyExtraction calls correct endpoint
 * 4. useApplyExtraction handles API errors
 * 5. useApplyExtraction invalidates KB cache on success
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client module
vi.mock("@/lib/api/extraction", () => ({
  extractionApi: {
    extractChapter: vi.fn(),
    applyExtraction: vi.fn(),
  },
}));

import { extractionApi } from "@/lib/api/extraction";
import { useApplyExtraction, useExtractChapter } from "@/lib/hooks/useExtraction";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const mockExtractChapter = extractionApi.extractChapter as ReturnType<typeof vi.fn>;
const mockApplyExtraction = extractionApi.applyExtraction as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockExtractionOutput = {
  results: [
    {
      item_type: "new_entity" as const,
      entity_type: "character",
      name: "Anna Schmidt",
      confidence: 0.92,
      source_text: "She walked through the old archive.",
      proposed_content: { role: "Protagonist" },
      target_entity_id: null,
      conflict_description: null,
      relationship_type: null,
      related_entity_name: null,
    },
  ],
  analysis_notes: "Found 1 new entity.",
};

const mockApplyResponse = {
  created_entries: [{ id: "entry-1", name: "Anna Schmidt", entity_type: "character" }],
  updated_entries: [],
};

const mockApplyItems = [
  {
    item_type: "new_entity" as const,
    name: "Anna Schmidt",
    entity_type: "character",
    proposed_content: { role: "Protagonist" },
    target_entity_id: null,
    relationship_type: null,
    related_entity_name: null,
    source_text: "She walked through the old archive.",
  },
];

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

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

function createWrapperWithClient(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useExtractChapter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls extractionApi.extractChapter with novelId and chapterId", async () => {
    mockExtractChapter.mockResolvedValueOnce(mockExtractionOutput);

    const { result } = renderHook(() => useExtractChapter("novel-1", "chapter-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockExtractChapter).toHaveBeenCalledWith(
      "novel-1",
      "chapter-1",
      expect.any(AbortSignal),
    );
    expect(result.current.data).toEqual(mockExtractionOutput);
  });

  it("handles API errors", async () => {
    mockExtractChapter.mockRejectedValueOnce(new Error("Extraction failed"));

    const { result } = renderHook(() => useExtractChapter("novel-1", "chapter-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Extraction failed");
  });

  it("returns extraction output on success", async () => {
    mockExtractChapter.mockResolvedValueOnce(mockExtractionOutput);

    const { result } = renderHook(() => useExtractChapter("novel-1", "chapter-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.data).toEqual(mockExtractionOutput);
    });

    // Verify the results array is present
    expect(result.current.data?.results).toHaveLength(1);
    expect(result.current.data?.results[0].name).toBe("Anna Schmidt");
    expect(result.current.data?.analysis_notes).toBe("Found 1 new entity.");
  });
});

describe("useApplyExtraction", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls extractionApi.applyExtraction with novelId and items", async () => {
    mockApplyExtraction.mockResolvedValueOnce(mockApplyResponse);

    const { result } = renderHook(() => useApplyExtraction("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockApplyItems);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockApplyExtraction).toHaveBeenCalledWith(
      "novel-1",
      mockApplyItems,
      expect.any(AbortSignal),
    );
    expect(result.current.data).toEqual(mockApplyResponse);
  });

  it("handles API errors", async () => {
    mockApplyExtraction.mockRejectedValueOnce(new Error("Apply failed"));

    const { result } = renderHook(() => useApplyExtraction("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockApplyItems);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Apply failed");
  });

  it("invalidates KB cache on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
        mutations: { retry: false },
      },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    mockApplyExtraction.mockResolvedValueOnce(mockApplyResponse);

    const { result } = renderHook(() => useApplyExtraction("novel-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate(mockApplyItems);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Should invalidate KB query keys for this novel
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["kb", "novel-1"],
    });
  });

  it("does not invalidate KB cache on failure", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
        mutations: { retry: false },
      },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    mockApplyExtraction.mockRejectedValueOnce(new Error("Apply failed"));

    const { result } = renderHook(() => useApplyExtraction("novel-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate(mockApplyItems);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    // Should NOT have invalidated on failure
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it("returns apply response with created and updated entries", async () => {
    mockApplyExtraction.mockResolvedValueOnce(mockApplyResponse);

    const { result } = renderHook(() => useApplyExtraction("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockApplyItems);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.created_entries).toHaveLength(1);
    expect(result.current.data?.created_entries[0].name).toBe("Anna Schmidt");
    expect(result.current.data?.updated_entries).toHaveLength(0);
  });
});
