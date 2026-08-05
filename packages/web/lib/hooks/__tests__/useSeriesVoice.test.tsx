/**
 * useSeriesVoice hook tests — TanStack Query hooks for the Series Voice
 * Hierarchy (Spec 3, Tasks 5–6).
 *
 * Covers the four hooks backing the series-voice lifecycle:
 *   - useSeriesVoice (GET; disabled when no seriesId)
 *   - useProfileSeriesVoice (POST profile-from-novel)
 *   - useUpdateSeriesVoiceOverride (PATCH manual override)
 *   - useClearSeriesVoiceOverride (DELETE override)
 *
 * Mirrors the useSeries.test.tsx conventions: hoisted vi.mock of the API
 * module, createWrapper() with a retry:false QueryClient, and cache
 * invalidation verified via a real spy on queryClient.invalidateQueries.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/series", () => ({
  seriesApi: {
    getVoice: vi.fn(),
    profileVoice: vi.fn(),
    updateVoiceOverride: vi.fn(),
    clearVoiceOverride: vi.fn(),
  },
}));

import { seriesApi } from "@/lib/api/series";
import {
  useClearSeriesVoiceOverride,
  useProfileSeriesVoice,
  useSeriesVoice,
  useUpdateSeriesVoiceOverride,
} from "@/lib/hooks/useSeriesVoice";

const mockGet = seriesApi.getVoice as ReturnType<typeof vi.fn>;
const mockProfile = seriesApi.profileVoice as ReturnType<typeof vi.fn>;
const mockUpdate = seriesApi.updateVoiceOverride as ReturnType<typeof vi.fn>;
const mockClear = seriesApi.clearVoiceOverride as ReturnType<typeof vi.fn>;

const SERIES_ID = "series-1";
const NOVEL_ID = "novel-1";

const profileFixture = {
  voice_analysis: {
    vocabulary_level: "literary",
    sentence_profile: "long, flowing",
    emotional_range: "melancholic",
  },
  author_examples: ["The rain fell like memory."],
  updated_at: "2026-08-04T10:00:00Z",
  is_fresh: true,
};

const voiceFixture = { series_id: SERIES_ID, author_voice: profileFixture };
const emptyFixture = { series_id: SERIES_ID, author_voice: null };

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

describe("useSeriesVoice", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("fetches the series voice via seriesApi.getVoice", async () => {
    mockGet.mockResolvedValueOnce(voiceFixture);

    const { result } = renderHook(() => useSeriesVoice(SERIES_ID), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith(SERIES_ID);
    expect(result.current.data?.author_voice).toEqual(profileFixture);
  });

  it("does not fetch when seriesId is empty", async () => {
    const { result } = renderHook(() => useSeriesVoice(""), { wrapper: createWrapper() });

    await Promise.resolve();
    expect(mockGet).not.toHaveBeenCalled();
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("carries a null author_voice when the series has no profile", async () => {
    mockGet.mockResolvedValueOnce(emptyFixture);

    const { result } = renderHook(() => useSeriesVoice(SERIES_ID), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.author_voice).toBeNull();
  });
});

describe("useProfileSeriesVoice", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("POSTs the profile request and invalidates the voice query", async () => {
    mockProfile.mockResolvedValueOnce({
      series_id: SERIES_ID,
      novel_id: NOVEL_ID,
      author_voice: profileFixture,
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useProfileSeriesVoice(SERIES_ID), {
      wrapper: createWrapper(queryClient),
    });

    result.current.mutate(NOVEL_ID);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockProfile).toHaveBeenCalledWith(SERIES_ID, NOVEL_ID);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["series", SERIES_ID, "voice"] });
  });
});

describe("useUpdateSeriesVoiceOverride", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("PATCHes the override dict and invalidates the voice query", async () => {
    const overrideRequest = { author_voice: { voice_analysis: { vocabulary_level: "plain" } } };
    mockUpdate.mockResolvedValueOnce({
      series_id: SERIES_ID,
      author_voice: overrideRequest.author_voice,
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdateSeriesVoiceOverride(SERIES_ID), {
      wrapper: createWrapper(queryClient),
    });

    result.current.mutate(overrideRequest);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockUpdate).toHaveBeenCalledWith(SERIES_ID, overrideRequest);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["series", SERIES_ID, "voice"] });
  });
});

describe("useClearSeriesVoiceOverride", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("DELETEs the override and invalidates the voice query", async () => {
    mockClear.mockResolvedValueOnce(undefined);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useClearSeriesVoiceOverride(SERIES_ID), {
      wrapper: createWrapper(queryClient),
    });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockClear).toHaveBeenCalledWith(SERIES_ID);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["series", SERIES_ID, "voice"] });
  });
});
