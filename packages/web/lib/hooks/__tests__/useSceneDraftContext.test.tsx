/**
 * useSceneDraftContext tests — the chapter context for the AI scene draft.
 *
 * Pins the W-D rewiring: ONE summary-only plan-context request replaces the
 * former up-to-three full-chapter GETs; `chapter_summary`/`neighbor_summaries`
 * compose from it in the compact format; storyboard (`structure_type`) and
 * outline (`outline_notes`) sources stay unchanged; every source degrades
 * independently down to the `{}` zero-context floor.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/planning", () => ({
  getStoryboard: vi.fn(),
  getOutline: vi.fn(),
}));
vi.mock("@/lib/api/client", () => ({
  chaptersApi: { get: vi.fn(), getPlanContext: vi.fn() },
}));

import { chaptersApi } from "@/lib/api/client";
import { getOutline, getStoryboard } from "@/lib/api/planning";
import { useSceneDraftContext } from "@/lib/hooks/useSceneDraftContext";
import type { OutlineResponse, StoryboardResponse } from "@/types";
import type { ChapterPlanContext } from "@/types/planning";

const mockedGetStoryboard = vi.mocked(getStoryboard);
const mockedGetOutline = vi.mocked(getOutline);
const mockedGetPlanContext = vi.mocked(chaptersApi.getPlanContext);
const mockedChapterGet = vi.mocked(chaptersApi.get);

const storyboardFixture: StoryboardResponse = {
  structure_type: "three_act",
  stages: [],
};

const outlineFixture: OutlineResponse = {
  id: "outline-1",
  chapter_id: "ch-1",
  stage_assignment: "act-2",
  outline_notes: "Focus on the gate siege",
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-02T00:00:00Z",
};

const planContextFixture: ChapterPlanContext = {
  chapter: { title: "The Gate", summary: "John reaches the gate." },
  previous: { title: "Storm", summary: "The fleet sails." },
  next: { title: "Ash", summary: "The city burns." },
};

function createWrapper() {
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

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("useSceneDraftContext", () => {
  it("issues exactly ONE plan-context request and NO chapter-detail GETs", async () => {
    mockedGetStoryboard.mockResolvedValue(storyboardFixture);
    mockedGetOutline.mockResolvedValue(outlineFixture);
    mockedGetPlanContext.mockResolvedValue(planContextFixture);

    const { result } = renderHook(() => useSceneDraftContext("novel-1", "ch-1"), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() =>
      expect(result.current).toMatchObject({ chapter_summary: "John reaches the gate." }),
    );

    expect(mockedGetPlanContext).toHaveBeenCalledTimes(1);
    expect(mockedGetPlanContext).toHaveBeenCalledWith("novel-1", "ch-1");
    expect(mockedChapterGet).not.toHaveBeenCalled();
  });

  it("caches under the plan-context key family nested below the chapter key", async () => {
    mockedGetStoryboard.mockResolvedValue(storyboardFixture);
    mockedGetOutline.mockResolvedValue(outlineFixture);
    mockedGetPlanContext.mockResolvedValue(planContextFixture);

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(() => useSceneDraftContext("novel-1", "ch-1"), {
      wrapper: Wrapper,
    });

    await waitFor(() => expect(result.current.chapter_summary).toBeDefined());

    const keys = queryClient
      .getQueryCache()
      .getAll()
      .map((query) => query.queryKey);
    expect(keys).toContainEqual(["novels", "novel-1", "chapters", "ch-1", "plan-context"]);
  });

  it("composes chapter_summary and neighbor_summaries in the compact format", async () => {
    mockedGetStoryboard.mockResolvedValue(storyboardFixture);
    mockedGetOutline.mockResolvedValue(outlineFixture);
    mockedGetPlanContext.mockResolvedValue(planContextFixture);

    const { result } = renderHook(() => useSceneDraftContext("novel-1", "ch-1"), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.neighbor_summaries).toBeDefined());

    expect(result.current).toEqual({
      structure_type: "three_act",
      outline_notes: "Focus on the gate siege",
      chapter_summary: "John reaches the gate.",
      neighbor_summaries:
        'Previous chapter "Storm": The fleet sails.\nNext chapter "Ash": The city burns.',
    });
  });

  it("omits neighbor lines for null edges and empty summaries", async () => {
    mockedGetStoryboard.mockResolvedValue(storyboardFixture);
    mockedGetOutline.mockResolvedValue(outlineFixture);
    mockedGetPlanContext.mockResolvedValue({
      chapter: { title: "The Gate", summary: "" },
      previous: null,
      next: { title: "Ash", summary: "" },
    });

    const { result } = renderHook(() => useSceneDraftContext("novel-1", "ch-1"), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.structure_type).toBeDefined());

    expect(result.current).toEqual({
      structure_type: "three_act",
      outline_notes: "Focus on the gate siege",
    });
  });

  it("degrades field-wise when the plan-context request fails", async () => {
    mockedGetStoryboard.mockResolvedValue(storyboardFixture);
    mockedGetOutline.mockResolvedValue(outlineFixture);
    mockedGetPlanContext.mockRejectedValue(new Error("plan-context unavailable"));

    const { result } = renderHook(() => useSceneDraftContext("novel-1", "ch-1"), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.structure_type).toBeDefined());

    expect(result.current).toEqual({
      structure_type: "three_act",
      outline_notes: "Focus on the gate siege",
    });
  });

  it("keeps the zero-context floor: all sources empty resolves to {}", async () => {
    mockedGetStoryboard.mockResolvedValue({ structure_type: "", stages: [] });
    mockedGetOutline.mockResolvedValue({ ...outlineFixture, outline_notes: "" });
    mockedGetPlanContext.mockResolvedValue({
      chapter: { title: "The Gate", summary: "" },
      previous: null,
      next: null,
    });

    const { result } = renderHook(() => useSceneDraftContext("novel-1", "ch-1"), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(mockedGetPlanContext).toHaveBeenCalled());

    expect(result.current).toEqual({});
  });

  it("does not fetch plan-context without a chapter and stays at the floor", () => {
    mockedGetStoryboard.mockResolvedValue(storyboardFixture);

    const { result } = renderHook(() => useSceneDraftContext("novel-1", null), {
      wrapper: createWrapper().Wrapper,
    });

    expect(mockedGetPlanContext).not.toHaveBeenCalled();
    expect(mockedGetOutline).not.toHaveBeenCalled();
    expect(result.current).toEqual({});
  });
});
