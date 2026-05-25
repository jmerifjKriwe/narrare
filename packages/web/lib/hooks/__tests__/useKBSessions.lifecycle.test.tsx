/**
 * useKBSessions hook tests — Session lifecycle hooks.
 *
 * Tests for TanStack Query hooks that manage session lifecycle:
 * - useCreateKBSession
 * - useKBSession
 * - useCompleteKBSession
 * - useAbandonKBSession
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client module
vi.mock("@/lib/api/kb-sessions", () => ({
  kbSessionApi: {
    createSession: vi.fn(),
    getSession: vi.fn(),
    answerField: vi.fn(),
    completeSession: vi.fn(),
    abandonSession: vi.fn(),
  },
  suggestField: vi.fn(),
  requestInterview: vi.fn(),
  requestEnhance: vi.fn(),
}));

import { kbSessionApi } from "@/lib/api/kb-sessions";
import {
  useAbandonKBSession,
  useCompleteKBSession,
  useCreateKBSession,
  useKBSession,
} from "@/lib/hooks/useKBSessions";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const mockCreateSession = kbSessionApi.createSession as ReturnType<typeof vi.fn>;
const mockGetSession = kbSessionApi.getSession as ReturnType<typeof vi.fn>;
const mockCompleteSession = kbSessionApi.completeSession as ReturnType<typeof vi.fn>;
const mockAbandonSession = kbSessionApi.abandonSession as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockSession = {
  id: "session-1",
  novel_id: "novel-1",
  user_id: "user-1",
  entity_type: "character",
  status: "active",
  fields: [
    {
      field_key: "name",
      label: "Name",
      field_type: "text",
      required: true,
      source: "user",
      user_value: undefined,
      ai_suggested_value: undefined,
      ai_reasoning: undefined,
      final_value: undefined,
    },
  ],
  context_entries: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

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

describe("useCreateKBSession", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls kbSessionApi.createSession with entity type", async () => {
    mockCreateSession.mockResolvedValueOnce(mockSession);

    const { result } = renderHook(() => useCreateKBSession("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate("character");

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockCreateSession).toHaveBeenCalledWith("novel-1", "character");
    expect(result.current.data).toEqual(mockSession);
  });

  it("caches the new session on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    // Spy on setQueryData
    const setQueryDataSpy = vi.spyOn(queryClient, "setQueryData");

    mockCreateSession.mockResolvedValueOnce(mockSession);

    const { result } = renderHook(() => useCreateKBSession("novel-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate("character");

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Should have cached the session data
    expect(setQueryDataSpy).toHaveBeenCalled();
    const callArgs = setQueryDataSpy.mock.calls.find(([key]) =>
      JSON.stringify(key).includes("session-1"),
    );
    expect(callArgs).toBeDefined();
  });

  it("handles API errors", async () => {
    mockCreateSession.mockRejectedValueOnce(new Error("Creation failed"));

    const { result } = renderHook(() => useCreateKBSession("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate("character");

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Creation failed");
  });
});

describe("useKBSession", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("fetches session when sessionId is provided", async () => {
    mockGetSession.mockResolvedValueOnce(mockSession);

    const { result } = renderHook(() => useKBSession("novel-1", "session-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGetSession).toHaveBeenCalledWith("novel-1", "session-1");
    expect(result.current.data).toEqual(mockSession);
  });

  it("does not fetch when sessionId is null", async () => {
    const { result } = renderHook(() => useKBSession("novel-1", null), {
      wrapper: createWrapper(),
    });

    // Should not be loading since query is disabled
    expect(result.current.isLoading).toBe(false);
    expect(mockGetSession).not.toHaveBeenCalled();
  });

  it("returns undefined when sessionId is null (query disabled)", async () => {
    mockGetSession.mockResolvedValueOnce(mockSession);

    const { result } = renderHook(() => useKBSession("novel-1", null), {
      wrapper: createWrapper(),
    });

    // When query is disabled, should not be loading
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(false);
    });
  });

  it("does not fetch when novelId is empty", async () => {
    const { result } = renderHook(() => useKBSession("", "session-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(mockGetSession).not.toHaveBeenCalled();
  });
});

describe("useCompleteKBSession", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls kbSessionApi.completeSession", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const removeSpy = vi.spyOn(queryClient, "removeQueries");

    mockCompleteSession.mockResolvedValueOnce(mockSession);

    const { result } = renderHook(() => useCompleteKBSession("novel-1", "session-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockCompleteSession).toHaveBeenCalledWith("novel-1", "session-1");

    // Should invalidate KB entries and remove session from cache
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["kb", "novel-1", "entries"],
    });
    expect(removeSpy).toHaveBeenCalled();
  });
});

describe("useAbandonKBSession", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls kbSessionApi.abandonSession and removes from cache", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const removeSpy = vi.spyOn(queryClient, "removeQueries");

    mockAbandonSession.mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useAbandonKBSession("novel-1", "session-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockAbandonSession).toHaveBeenCalledWith("novel-1", "session-1");
    expect(removeSpy).toHaveBeenCalled();
  });
});
