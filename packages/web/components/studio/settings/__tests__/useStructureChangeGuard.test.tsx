/**
 * useStructureChangeGuard hook tests.
 *
 * The hook encapsulates the "story-structure change requires a remap dialog"
 * guard that NovelDetailsTab previously inlined. Extracted (RULE-04) to make
 * room for the Spec 3 series-voice opt-out card without bloating the tab.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import type { Novel } from "@/types";
import { useStructureChangeGuard } from "../_components/useStructureChangeGuard";

const novel: Novel = {
  id: "novel-1",
  series_id: null,
  title: "T",
  author: "A",
  genre: "Fantasy",
  writing_language: "en",
  tone: "dramatic",
  story_structure: "three_act",
  logline: "",
  synopsis: "",
  is_demo: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function wrapper(client?: QueryClient) {
  const c = client ?? new QueryClient();
  return function W({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={c}>{children}</QueryClientProvider>;
  };
}

describe("useStructureChangeGuard", () => {
  it("does not intercept when the structure is unchanged", () => {
    const { result } = renderHook(() => useStructureChangeGuard({ novel }), { wrapper: wrapper() });
    const res = result.current.intercept({ title: "New", story_structure: "three_act" });
    expect(res.intercepted).toBe(false);
    expect(result.current.pendingStructure).toBeNull();
  });

  it("intercepts and opens the dialog when the structure changes", () => {
    const { result } = renderHook(() => useStructureChangeGuard({ novel }), { wrapper: wrapper() });
    let res: { intercepted: boolean; immediatePayload: Partial<Novel> } | undefined;
    act(() => {
      res = result.current.intercept({ story_structure: "five_act", title: "New" });
    });
    expect(res?.intercepted).toBe(true);
    expect(res?.immediatePayload).toEqual({ title: "New" });
    expect(result.current.pendingStructure).toBe("five_act");
    expect(result.current.remapDialogOpen).toBe(true);
  });

  it("returns the full payload (minus structure) as immediatePayload", () => {
    const { result } = renderHook(() => useStructureChangeGuard({ novel }), { wrapper: wrapper() });
    let res: { intercepted: boolean; immediatePayload: Partial<Novel> } | undefined;
    act(() => {
      res = result.current.intercept({ story_structure: "heros_journey" });
    });
    expect(res?.intercepted).toBe(true);
    expect(res?.immediatePayload).toEqual({});
  });

  it("does not intercept when the novel has not loaded", () => {
    const { result } = renderHook(() => useStructureChangeGuard({ novel: undefined }), {
      wrapper: wrapper(),
    });
    const res = result.current.intercept({ story_structure: "five_act" });
    expect(res.intercepted).toBe(false);
  });

  it("closes the dialog on close()", () => {
    const { result } = renderHook(() => useStructureChangeGuard({ novel }), { wrapper: wrapper() });
    act(() => result.current.intercept({ story_structure: "five_act" }));
    expect(result.current.pendingStructure).toBe("five_act");
    act(() => result.current.close());
    expect(result.current.pendingStructure).toBeNull();
    expect(result.current.remapDialogOpen).toBe(false);
  });
});
