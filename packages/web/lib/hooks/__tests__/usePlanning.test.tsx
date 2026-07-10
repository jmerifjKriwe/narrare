/**
 * usePlanning hook tests — TanStack Query hooks for storyboard & outlines.
 *
 * Tests: useStoryboard, useChapterOutline, useUpdateOutline, usePreviewRemap,
 * useConfirmRemap — fetch, disabled states, invalidation, and error paths.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/planning", () => ({
  getStoryboard: vi.fn(),
  getOutline: vi.fn(),
  updateOutline: vi.fn(),
  previewRemap: vi.fn(),
  confirmRemap: vi.fn(),
}));

import {
  confirmRemap,
  getOutline,
  getStoryboard,
  previewRemap,
  updateOutline,
} from "@/lib/api/planning";
import {
  useChapterOutline,
  useConfirmRemap,
  usePreviewRemap,
  useStoryboard,
  useUpdateOutline,
} from "@/lib/hooks/usePlanning";

const mockedGetStoryboard = vi.mocked(getStoryboard);
const mockedGetOutline = vi.mocked(getOutline);
const mockedUpdateOutline = vi.mocked(updateOutline);
const mockedPreviewRemap = vi.mocked(previewRemap);
const mockedConfirmRemap = vi.mocked(confirmRemap);

const storyboardFixture = { stages: [] } as never;
const outlineFixture = { chapter_id: "ch-1", beats: [] } as never;
const remapFixture = { preview: true, changes: [] } as never;

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

describe("useStoryboard", () => {
  it("fetches the storyboard for a novel", async () => {
    mockedGetStoryboard.mockResolvedValueOnce(storyboardFixture);

    const { result } = renderHook(() => useStoryboard("novel-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockedGetStoryboard).toHaveBeenCalledWith("novel-1");
    expect(result.current.data).toBe(storyboardFixture);
  });

  it("is disabled when novelId is empty", () => {
    const { result } = renderHook(() => useStoryboard(""), { wrapper: createWrapper() });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockedGetStoryboard).not.toHaveBeenCalled();
  });
});

describe("useChapterOutline", () => {
  it("fetches the outline for a chapter", async () => {
    mockedGetOutline.mockResolvedValueOnce(outlineFixture);

    const { result } = renderHook(() => useChapterOutline("novel-1", "ch-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockedGetOutline).toHaveBeenCalledWith("novel-1", "ch-1");
    expect(result.current.data).toBe(outlineFixture);
  });

  it("is disabled when chapterId is null", () => {
    const { result } = renderHook(() => useChapterOutline("novel-1", null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockedGetOutline).not.toHaveBeenCalled();
  });
});

describe("useUpdateOutline", () => {
  it("updates the outline and invalidates storyboard + outline caches", async () => {
    mockedUpdateOutline.mockResolvedValueOnce(outlineFixture);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useUpdateOutline("novel-1"), {
      wrapper: createWrapper(),
    });

    const data = { stage_id: "s1" } as never;
    result.current.mutate({ chapterId: "ch-1", data });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockedUpdateOutline).toHaveBeenCalledWith("novel-1", "ch-1", data);
    expect(invalidateSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
    invalidateSpy.mockRestore();
  });

  it("propagates API errors", async () => {
    mockedUpdateOutline.mockRejectedValueOnce(new Error("Update failed"));

    const { result } = renderHook(() => useUpdateOutline("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ chapterId: "ch-1", data: {} as never });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Update failed");
  });
});

describe("usePreviewRemap", () => {
  it("previews a remap", async () => {
    mockedPreviewRemap.mockResolvedValueOnce(remapFixture);

    const { result } = renderHook(() => usePreviewRemap("novel-1", "act"), {
      wrapper: createWrapper(),
    });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockedPreviewRemap).toHaveBeenCalledWith("novel-1", "act");
    expect(result.current.data).toBe(remapFixture);
  });
});

describe("useConfirmRemap", () => {
  it("confirms a remap and invalidates storyboard + novel caches", async () => {
    mockedConfirmRemap.mockResolvedValueOnce(remapFixture);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useConfirmRemap("novel-1", "act"), {
      wrapper: createWrapper(),
    });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockedConfirmRemap).toHaveBeenCalledWith("novel-1", "act");
    expect(invalidateSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
    invalidateSpy.mockRestore();
  });
});
