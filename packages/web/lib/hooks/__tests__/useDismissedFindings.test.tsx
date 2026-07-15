/**
 * useDismissedFindings hook tests (CR-AUFG-07-26).
 *
 * Tests:
 * 1. Fetches dismissed fingerprints and exposes them as a Set
 * 2. isLoading reflects the query state
 * 3. dismiss mutation calls consistencyApi.dismissFinding
 * 4. dismiss invalidates the dismissed query cache
 * 5. undismiss mutation calls consistencyApi.undismissFinding
 * 6. undismiss invalidates the dismissed query cache
 * 7. Returns empty Set when no fingerprints dismissed
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client module
vi.mock("@/lib/api/consistency", () => ({
  consistencyApi: {
    dismissFinding: vi.fn(),
    listDismissed: vi.fn(),
    undismissFinding: vi.fn(),
  },
}));

import { consistencyApi } from "@/lib/api/consistency";
import { useDismissedFindings } from "@/lib/hooks/useDismissedFindings";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const mockListDismissed = consistencyApi.listDismissed as ReturnType<typeof vi.fn>;
const mockDismissFinding = consistencyApi.dismissFinding as ReturnType<typeof vi.fn>;
const mockUndismissFinding = consistencyApi.undismissFinding as ReturnType<typeof vi.fn>;

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

function createWrapperWithClient() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return {
    queryClient,
    Wrapper: function Wrapper({ children }: { children: ReactNode }) {
      return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    },
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useDismissedFindings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("fetches dismissed fingerprints and exposes them as a Set", async () => {
    mockListDismissed.mockResolvedValueOnce({ fingerprints: ["fp1::a,b", "fp2::c"] });

    const { result } = renderHook(() => useDismissedFindings("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockListDismissed).toHaveBeenCalledWith("novel-1");
    expect(result.current.dismissedFingerprints).toBeInstanceOf(Set);
    expect(result.current.dismissedFingerprints.has("fp1::a,b")).toBe(true);
    expect(result.current.dismissedFingerprints.has("fp2::c")).toBe(true);
    expect(result.current.dismissedFingerprints.size).toBe(2);
  });

  it("returns empty Set when no fingerprints dismissed", async () => {
    mockListDismissed.mockResolvedValueOnce({ fingerprints: [] });

    const { result } = renderHook(() => useDismissedFindings("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.dismissedFingerprints.size).toBe(0);
  });

  it("dismiss mutation calls consistencyApi.dismissFinding", async () => {
    mockListDismissed.mockResolvedValue({ fingerprints: [] });
    mockDismissFinding.mockResolvedValueOnce({ success: true });

    const { result } = renderHook(() => useDismissedFindings("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    result.current.dismiss("desc::Anna,Johann");

    await waitFor(() => {
      expect(mockDismissFinding).toHaveBeenCalledWith("novel-1", {
        fingerprint: "desc::Anna,Johann",
      });
    });
  });

  it("dismiss invalidates the dismissed query cache", async () => {
    const { queryClient, Wrapper } = createWrapperWithClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    mockListDismissed.mockResolvedValue({ fingerprints: [] });
    mockDismissFinding.mockResolvedValueOnce({ success: true });

    const { result } = renderHook(() => useDismissedFindings("novel-1"), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    result.current.dismiss("fp1");

    await waitFor(() => {
      expect(mockDismissFinding).toHaveBeenCalled();
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["kb", "novel-1", "dismissed"],
    });
  });

  it("undismiss mutation calls consistencyApi.undismissFinding", async () => {
    mockListDismissed.mockResolvedValue({ fingerprints: [] });
    mockUndismissFinding.mockResolvedValueOnce({ success: true });

    const { result } = renderHook(() => useDismissedFindings("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    result.current.undismiss("fp-to-restore");

    await waitFor(() => {
      expect(mockUndismissFinding).toHaveBeenCalledWith("novel-1", "fp-to-restore");
    });
  });

  it("undismiss invalidates the dismissed query cache", async () => {
    const { queryClient, Wrapper } = createWrapperWithClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    mockListDismissed.mockResolvedValue({ fingerprints: [] });
    mockUndismissFinding.mockResolvedValueOnce({ success: true });

    const { result } = renderHook(() => useDismissedFindings("novel-1"), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    result.current.undismiss("fp1");

    await waitFor(() => {
      expect(mockUndismissFinding).toHaveBeenCalled();
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["kb", "novel-1", "dismissed"],
    });
  });
});
