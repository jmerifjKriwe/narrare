/**
 * useKBSessions hook tests — Session action hooks.
 *
 * Tests for TanStack Query hooks that perform session actions:
 * - useAnswerField
 * - useKBSessionSuggest
 * - useKBSessionInterview
 * - useKBSessionEnhance
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

import {
  kbSessionApi,
  requestEnhance,
  requestInterview,
  suggestField,
} from "@/lib/api/kb-sessions";
import {
  useAnswerField,
  useKBSessionEnhance,
  useKBSessionInterview,
  useKBSessionSuggest,
} from "@/lib/hooks/useKBSessions";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const mockAnswerField = kbSessionApi.answerField as ReturnType<typeof vi.fn>;
const mockSuggestField = suggestField as ReturnType<typeof vi.fn>;
const mockRequestInterview = requestInterview as ReturnType<typeof vi.fn>;
const mockRequestEnhance = requestEnhance as ReturnType<typeof vi.fn>;

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

const mockSuggestion = {
  field_key: "name",
  suggestion: "Anna Schmidt",
  reasoning: "Common name.",
};

const mockInterviewResult = {
  question: "What is the name?",
  target_field: "name",
  context: "",
};

const mockEnhancementResults = [
  {
    field_key: "description",
    original: "A hero",
    suggested: "A brave hero",
    reasoning: "More descriptive.",
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

describe("useAnswerField", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls kbSessionApi.answerField with correct args", async () => {
    mockAnswerField.mockResolvedValueOnce(mockSession);

    const { result } = renderHook(() => useAnswerField("novel-1", "session-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ fieldKey: "name", value: "Anna" });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockAnswerField).toHaveBeenCalledWith("novel-1", "session-1", "name", "Anna");
  });
});

describe("useKBSessionSuggest", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls suggestField and invalidates session cache on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    mockSuggestField.mockResolvedValueOnce(mockSuggestion);

    const { result } = renderHook(() => useKBSessionSuggest("novel-1", "session-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate({ fieldKey: "name" });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockSuggestField).toHaveBeenCalledWith("novel-1", "session-1", "name", undefined);
    expect(result.current.data).toEqual(mockSuggestion);

    // Should invalidate session query
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["kb-sessions", "novel-1", "sessions", "session-1"],
    });
  });

  it("passes abort signal when provided", async () => {
    mockSuggestField.mockResolvedValueOnce(mockSuggestion);

    const { result } = renderHook(() => useKBSessionSuggest("novel-1", "session-1"), {
      wrapper: createWrapper(),
    });

    const controller = new AbortController();
    result.current.mutate({ fieldKey: "name", signal: controller.signal });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockSuggestField).toHaveBeenCalledWith(
      "novel-1",
      "session-1",
      "name",
      controller.signal,
    );
  });

  it("handles API errors", async () => {
    mockSuggestField.mockRejectedValueOnce(new Error("Suggestion failed"));

    const { result } = renderHook(() => useKBSessionSuggest("novel-1", "session-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ fieldKey: "name" });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Suggestion failed");
  });
});

describe("useKBSessionInterview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls requestInterview and invalidates session cache", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    mockRequestInterview.mockResolvedValueOnce(mockInterviewResult);

    const { result } = renderHook(() => useKBSessionInterview("novel-1", "session-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockRequestInterview).toHaveBeenCalledWith("novel-1", "session-1", undefined);
    expect(result.current.data).toEqual(mockInterviewResult);

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["kb-sessions", "novel-1", "sessions", "session-1"],
    });
  });

  it("passes abort signal", async () => {
    mockRequestInterview.mockResolvedValueOnce(mockInterviewResult);

    const { result } = renderHook(() => useKBSessionInterview("novel-1", "session-1"), {
      wrapper: createWrapper(),
    });

    const controller = new AbortController();
    result.current.mutate(controller.signal);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockRequestInterview).toHaveBeenCalledWith("novel-1", "session-1", controller.signal);
  });
});

describe("useKBSessionEnhance", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls requestEnhance and invalidates session cache", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    mockRequestEnhance.mockResolvedValueOnce(mockEnhancementResults);

    const { result } = renderHook(() => useKBSessionEnhance("novel-1", "session-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockRequestEnhance).toHaveBeenCalledWith("novel-1", "session-1", undefined);
    expect(result.current.data).toEqual(mockEnhancementResults);

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["kb-sessions", "novel-1", "sessions", "session-1"],
    });
  });

  it("passes abort signal", async () => {
    mockRequestEnhance.mockResolvedValueOnce(mockEnhancementResults);

    const { result } = renderHook(() => useKBSessionEnhance("novel-1", "session-1"), {
      wrapper: createWrapper(),
    });

    const controller = new AbortController();
    result.current.mutate(controller.signal);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockRequestEnhance).toHaveBeenCalledWith("novel-1", "session-1", controller.signal);
  });
});
