// @vitest-environment jsdom
/**
 * The workspace's read seam (W4 Task 11): the pure helpers that turn the
 * chapters list and the per-chapter scene answers into the tree's ordered
 * entries, the last-edited scene the hero door and the active marker share,
 * the tension card's real scene codes and the storyboard's stage label.
 * The figures are the rows' own — never the draft's mock numbers.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

import { client, type Chapter, type Scene, type Storyboard } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { queryClient } from "@shell/lib/query";

import {
  lastEditedEntry,
  orderedSceneEntries,
  sceneCodeNumbers,
  stageTitleKey,
  tensionCodes,
  useChapterScenes,
  useScenesQuery,
  useStoryboardQuery,
} from "./workspace";

const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

function chapterRow(overrides: Partial<Chapter> & { id: string }): Chapter {
  return {
    novel_id: "11111111-1111-1111-1111-111111111111",
    title: "Kapitel",
    position: 0,
    scene_count: 0,
    word_count: 0,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-10T10:00:00Z",
    ...overrides,
  };
}

function sceneRow(overrides: Partial<Scene> & { id: string; chapter_id: string }): Scene {
  return {
    title: "Szene",
    body: "Prosa",
    setting: null,
    story_time: null,
    position: 1,
    word_count: 1,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-10T10:00:00Z",
    ...overrides,
  };
}

const CH1 = chapterRow({ id: "c1", position: 0, title: "Ghost in the Machine" });
const CH2 = chapterRow({ id: "c2", position: 1, title: "Nevada Echoes" });
const S11 = sceneRow({ id: "s11", chapter_id: "c1", position: 1, updated_at: "2026-11-11T08:00:00Z" });
const S12 = sceneRow({ id: "s12", chapter_id: "c1", position: 2, updated_at: "2026-11-14T09:30:00Z" });
const S21 = sceneRow({ id: "s21", chapter_id: "c2", position: 1, updated_at: "2026-11-12T07:00:00Z" });

/** The storyboard as planning's API answers it: the default three-act
 *  structure, the first chapter suggested into the setup stage. */
const STORYBOARD: Storyboard = {
  novel_id: "11111111-1111-1111-1111-111111111111",
  structure_id: "three-act",
  stages: [
    {
      key: "setup",
      title_key: "storyboard.stage.setup",
      from: 0,
      to: 0.25,
      chapters: [
        {
          chapter_id: "c1",
          title: "Ghost in the Machine",
          position: 0,
          stage_key: "setup",
          assignment_source: "suggested",
          sync_status: "planned",
          word_count: 765,
        },
      ],
    },
    { key: "confrontation", title_key: "storyboard.stage.confrontation", from: 0.25, to: 0.75, chapters: [] },
    { key: "resolution", title_key: "storyboard.stage.resolution", from: 0.75, to: 1, chapters: [] },
  ],
};

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
});

describe("orderedSceneEntries", () => {
  it("walks chapters in their order and scenes in position order", () => {
    const byChapter = new Map<string, Scene[]>([
      ["c1", [S12, S11]], // the answer may arrive unsorted; position decides
      ["c2", [S21]],
    ]);
    const entries = orderedSceneEntries([CH1, CH2], byChapter);
    expect(entries.map((entry) => entry.scene.id)).toEqual(["s11", "s12", "s21"]);
    expect(entries[0].chapter.id).toBe("c1");
    expect(entries[2].chapter.id).toBe("c2");
  });

  it("an empty chapter contributes no entries but keeps its place", () => {
    const entries = orderedSceneEntries([CH1, CH2], new Map([["c1", [S11]]]));
    expect(entries.map((entry) => entry.scene.id)).toEqual(["s11"]);
  });

  it("no chapters, no entries", () => {
    expect(orderedSceneEntries([], new Map())).toEqual([]);
  });
});

describe("lastEditedEntry", () => {
  it("picks the latest updated_at as parsed instants, not string order", () => {
    const entries = orderedSceneEntries(
      [CH1, CH2],
      new Map([
        ["c1", [S11, S12]],
        // A different timezone offset: the string sorts before S12's, the
        // instant is after it — the parse is what decides.
        ["c2", [sceneRow({ id: "s21", chapter_id: "c2", position: 1, updated_at: "2026-11-14T08:00:00-05:00" })]],
      ]),
    );
    expect(lastEditedEntry(entries)?.scene.id).toBe("s21");
  });

  it("ties keep the first entry in position order", () => {
    const tie = sceneRow({ id: "s21", chapter_id: "c2", position: 1, updated_at: S12.updated_at });
    const entries = orderedSceneEntries([CH1, CH2], new Map([["c1", [S11, S12]], ["c2", [tie]]]));
    expect(lastEditedEntry(entries)?.scene.id).toBe("s12");
  });

  it("an empty book has no last-edited scene", () => {
    expect(lastEditedEntry([])).toBeNull();
  });
});

describe("sceneCodeNumbers", () => {
  it("counts chapters and scenes from one, the draft's K1-S2 badge", () => {
    const entries = orderedSceneEntries([CH1, CH2], new Map([["c1", [S11, S12]], ["c2", [S21]]]));
    expect(sceneCodeNumbers(entries[1])).toEqual({ chapter: 1, scene: 2 });
    expect(sceneCodeNumbers(entries[2])).toEqual({ chapter: 2, scene: 1 });
  });
});

describe("tensionCodes", () => {
  const entries = orderedSceneEntries([CH1, CH2], new Map([["c1", [S11, S12]], ["c2", [S21]]]));

  it("names the first, the active and the last scene — the active marked", () => {
    const codes = tensionCodes(entries, entries[1]);
    expect(codes).toEqual([
      { chapter: 1, scene: 1, active: false },
      { chapter: 1, scene: 2, active: true },
      { chapter: 2, scene: 1, active: false },
    ]);
  });

  it("deduplicates when the active scene is the first or the last", () => {
    expect(tensionCodes(entries, entries[0])).toEqual([
      { chapter: 1, scene: 1, active: true },
      { chapter: 2, scene: 1, active: false },
    ]);
    expect(tensionCodes(entries, entries[2])).toEqual([
      { chapter: 1, scene: 1, active: false },
      { chapter: 2, scene: 1, active: true },
    ]);
  });

  it("a single scene stands once, active", () => {
    const one = orderedSceneEntries([CH1], new Map([["c1", [S11]]]));
    expect(tensionCodes(one, one[0])).toEqual([{ chapter: 1, scene: 1, active: true }]);
  });

  it("no scenes, no codes — the card keeps its neutral", () => {
    expect(tensionCodes([], null)).toEqual([]);
  });
});

describe("stageTitleKey", () => {
  it("resolves the staged chapter's stage title key from the catalog", () => {
    const key = stageTitleKey(STORYBOARD, "c1");
    expect(key).toBe("storyboard.stage.setup");
    expect(catalogs.de[key as keyof typeof catalogs.de]).toBeTruthy();
  });

  it("an unstaged chapter keeps the neutral", () => {
    expect(stageTitleKey(STORYBOARD, "c2")).toBeNull();
  });

  it("an unknown title key never reaches the message function", () => {
    const drifted: Storyboard = {
      ...STORYBOARD,
      stages: [{ ...STORYBOARD.stages[0], title_key: "storyboard.stage.unknown" }],
    };
    expect(stageTitleKey(drifted, "c1")).toBeNull();
  });

  it("no storyboard, no label", () => {
    expect(stageTitleKey(null, "c1")).toBeNull();
  });
});

describe("the scene reads", () => {
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  beforeEach(() => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/chapters/{chapter_id}/scenes") {
        return { data: [S11, S12], response: ok() };
      }
      if (path === "/api/planning/novels/{novel_id}/storyboard") {
        return { data: STORYBOARD, response: ok() };
      }
      throw new Error(`unexpected request: ${path}`);
    });
  });

  it("useScenesQuery asks the chapter's scenes and caches under the chapter", async () => {
    const { result } = renderHook(() => useScenesQuery("c1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.map((scene) => scene.id)).toEqual(["s11", "s12"]);
    expect(api.GET).toHaveBeenCalledWith("/api/writing/chapters/{chapter_id}/scenes", {
      params: { path: { chapter_id: "c1" } },
    });
    expect(queryClient.getQueryData(["scenes", "c1"])).toEqual([S11, S12]);
  });

  it("useScenesQuery throws on a refusal — never a half-current list", async () => {
    api.GET.mockImplementation(async () => ({ data: undefined, response: new Response(null, { status: 503 }) }));
    const { result } = renderHook(() => useScenesQuery("c1"), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("useChapterScenes asks one question per chapter, aligned with the list", async () => {
    const { result } = renderHook(() => useChapterScenes([CH1, CH2]), { wrapper });
    await waitFor(() => expect(result.current.every((query) => query.isSuccess)).toBe(true));
    expect(result.current).toHaveLength(2);
    expect(api.GET).toHaveBeenCalledTimes(2);
  });

  it("useChapterScenes with no chapters asks nothing", () => {
    const { result } = renderHook(() => useChapterScenes([]), { wrapper });
    expect(result.current).toEqual([]);
    expect(api.GET).not.toHaveBeenCalled();
  });

  it("useStoryboardQuery reads planning's HTTP surface — no capability import", async () => {
    const { result } = renderHook(() => useStoryboardQuery("11111111-1111-1111-1111-111111111111"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.structure_id).toBe("three-act");
    expect(api.GET).toHaveBeenCalledWith("/api/planning/novels/{novel_id}/storyboard", {
      params: { path: { novel_id: "11111111-1111-1111-1111-111111111111" } },
    });
  });

  it("useStoryboardQuery throws on a refusal — the label keeps its neutral", async () => {
    api.GET.mockImplementation(async () => ({ data: undefined, response: new Response(null, { status: 500 }) }));
    const { result } = renderHook(() => useStoryboardQuery("n1"), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
