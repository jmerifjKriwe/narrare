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
  invalidateSceneReads,
  invalidateStructureReads,
  lastEditedEntry,
  movedIds,
  orderedSceneEntries,
  rowsInOrder,
  sceneCodeNumbers,
  stageTitleKey,
  tensionCodes,
  useChapterScenes,
  useCreateChapter,
  useCreateScene,
  useDeleteChapter,
  useDeleteScene,
  useReorderChapters,
  useReorderScenes,
  useStoryboardQuery,
  useUpdateChapter,
  useUpdateScene,
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

  it("a one-chapter list asks the chapter's scenes and caches under the chapter", async () => {
    const { result } = renderHook(() => useChapterScenes([CH1]), { wrapper });
    await waitFor(() => expect(result.current[0].isSuccess).toBe(true));
    expect(result.current[0].data?.map((scene) => scene.id)).toEqual(["s11", "s12"]);
    expect(api.GET).toHaveBeenCalledWith("/api/writing/chapters/{chapter_id}/scenes", {
      params: { path: { chapter_id: "c1" } },
    });
    expect(queryClient.getQueryData(["scenes", "c1"])).toEqual([S11, S12]);
  });

  it("a refusal throws — never a half-current list", async () => {
    api.GET.mockImplementation(async () => ({ data: undefined, response: new Response(null, { status: 503 }) }));
    const { result } = renderHook(() => useChapterScenes([CH1]), { wrapper });
    await waitFor(() => expect(result.current[0].isError).toBe(true));
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

// --- Task 13: the write seam — the tree's CRUD doors and reorder ----------

describe("movedIds — the whole order one drag asks for", () => {
  const ids = ["a", "b", "c", "d"];

  it("moves a row before its target (dragging up)", () => {
    expect(movedIds(ids, "c", "a", true)).toEqual(["c", "a", "b", "d"]);
  });

  it("moves a row after its target (dragging down)", () => {
    expect(movedIds(ids, "a", "c", false)).toEqual(["b", "c", "a", "d"]);
  });

  it("a row dropped on itself keeps the order — no write owed", () => {
    expect(movedIds(ids, "b", "b", true)).toEqual(ids);
    expect(movedIds(ids, "b", "b", false)).toEqual(ids);
  });

  it("an id the order does not hold keeps the order — nothing invented", () => {
    expect(movedIds(ids, "x", "a", true)).toEqual(ids);
    expect(movedIds(ids, "a", "x", false)).toEqual(ids);
  });

  it("the keyboard's one-step move is the same helper — up before, down after", () => {
    // ArrowUp on c: before its predecessor b. ArrowDown on b: after c.
    expect(movedIds(ids, "c", "b", true)).toEqual(["a", "c", "b", "d"]);
    expect(movedIds(ids, "b", "c", false)).toEqual(["a", "c", "b", "d"]);
  });
});

describe("rowsInOrder — the cache write an arrangement asks for", () => {
  it("renumbers chapters from zero in the ids' order, keeping every other field", () => {
    const rows = rowsInOrder([CH1, CH2], ["c2", "c1"], 0);
    expect(rows?.map((row) => row.id)).toEqual(["c2", "c1"]);
    expect(rows?.map((row) => row.position)).toEqual([0, 1]);
    expect(rows?.[0].title).toBe("Nevada Echoes");
    expect(rows?.[0].word_count).toBe(CH2.word_count);
  });

  it("renumbers scenes from one — the position IS the ordinal", () => {
    const rows = rowsInOrder([S11, S12], ["s12", "s11"], 1);
    expect(rows?.map((row) => row.position)).toEqual([1, 2]);
    expect(rows?.[0].id).toBe("s12");
  });

  it("an id the cache lacks answers null — the caller refetches, never invents", () => {
    expect(rowsInOrder([CH1], ["c1", "c2"], 0)).toBeNull();
    expect(rowsInOrder([S11, S12], ["s11"], 1)).toBeNull();
  });
});

describe("the invalidation seams", () => {
  it("a structure write asks the chapters, the novels family and the activity", () => {
    const spy = vi.spyOn(queryClient, "invalidateQueries");
    invalidateStructureReads("n1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["chapters", "n1"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["novels"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["activity"] });
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ["scenes", "c1"] });
    spy.mockRestore();
  });

  it("a scene write asks the scene's list beside the structure family (Task 12's seam, unchanged)", () => {
    const spy = vi.spyOn(queryClient, "invalidateQueries");
    invalidateSceneReads("c1", "n1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["scenes", "c1"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["chapters", "n1"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["novels"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["activity"] });
    spy.mockRestore();
  });
});

describe("the CRUD mutations", () => {
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  let invalidated: (readonly unknown[])[];
  let removed: (readonly unknown[])[];

  beforeEach(() => {
    invalidated = [];
    removed = [];
    vi.spyOn(queryClient, "invalidateQueries").mockImplementation((filters?: { queryKey?: readonly unknown[] }) => {
      invalidated.push(filters?.queryKey ?? []);
      return Promise.resolve();
    });
    vi.spyOn(queryClient, "removeQueries").mockImplementation((filters?: { queryKey?: readonly unknown[] }) => {
      removed.push(filters?.queryKey ?? []);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function refusal(status: number, body?: unknown): { data: undefined; error: unknown; response: Response } {
    return {
      data: undefined,
      error: body,
      response: new Response(null, { status }),
    };
  }

  it("createChapter posts the honest empty title and asks the structure family", async () => {
    api.POST.mockResolvedValue({ data: { ...CH1, id: "c3", title: "" }, response: ok() });
    const { result } = renderHook(() => useCreateChapter("n1"), { wrapper });
    const created = await result.current.mutateAsync();
    expect(created.id).toBe("c3");
    expect(api.POST).toHaveBeenCalledWith("/api/writing/novels/{novel_id}/chapters", {
      params: { path: { novel_id: "n1" } },
      body: { title: "" },
    });
    expect(invalidated).toContainEqual(["chapters", "n1"]);
    expect(invalidated).toContainEqual(["novels"]);
    expect(invalidated).toContainEqual(["activity"]);
  });

  it("createScene posts the empty scene under its chapter and asks the scene family", async () => {
    api.POST.mockResolvedValue({ data: { ...S11, id: "s3" }, response: ok() });
    const { result } = renderHook(() => useCreateScene("n1"), { wrapper });
    await result.current.mutateAsync({ chapterId: "c1" });
    expect(api.POST).toHaveBeenCalledWith("/api/writing/chapters/{chapter_id}/scenes", {
      params: { path: { chapter_id: "c1" } },
      body: { title: "", body: "" },
    });
    expect(invalidated).toContainEqual(["scenes", "c1"]);
    expect(invalidated).toContainEqual(["chapters", "n1"]);
    expect(invalidated).toContainEqual(["novels"]);
    expect(invalidated).toContainEqual(["activity"]);
  });

  it("updateChapter carries the title alone and asks the structure family", async () => {
    api.PUT.mockResolvedValue({ data: { ...CH1, title: "Neu" }, response: ok() });
    const { result } = renderHook(() => useUpdateChapter("n1"), { wrapper });
    await result.current.mutateAsync({ chapterId: "c1", title: "Neu" });
    expect(api.PUT).toHaveBeenCalledWith("/api/writing/chapters/{chapter_id}", {
      params: { path: { chapter_id: "c1" } },
      body: { title: "Neu" },
    });
    expect(invalidated).toContainEqual(["chapters", "n1"]);
    expect(invalidated).toContainEqual(["novels"]);
  });

  it("updateScene carries only the changed fields — a carried null clears a label", async () => {
    api.PUT.mockResolvedValue({ data: { ...S11, setting: null }, response: ok() });
    const { result } = renderHook(() => useUpdateScene("n1"), { wrapper });
    await result.current.mutateAsync({
      sceneId: "s11",
      chapterId: "c1",
      changes: { title: "Neu", setting: null, story_time: "Dritte Stunde" },
    });
    expect(api.PUT).toHaveBeenCalledWith("/api/writing/scenes/{scene_id}", {
      params: { path: { scene_id: "s11" } },
      body: { title: "Neu", setting: null, story_time: "Dritte Stunde" },
    });
    expect(invalidated).toContainEqual(["scenes", "c1"]);
    expect(invalidated).toContainEqual(["chapters", "n1"]);
  });

  it("deleteChapter removes the row, asks the structure family and retires the dead scene list", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: new Response(null, { status: 204 }) });
    const { result } = renderHook(() => useDeleteChapter("n1"), { wrapper });
    await result.current.mutateAsync("c1");
    expect(api.DELETE).toHaveBeenCalledWith("/api/writing/chapters/{chapter_id}", {
      params: { path: { chapter_id: "c1" } },
    });
    expect(invalidated).toContainEqual(["chapters", "n1"]);
    expect(invalidated).toContainEqual(["novels"]);
    expect(invalidated).toContainEqual(["activity"]);
    expect(removed).toContainEqual(["scenes", "c1"]);
  });

  it("deleteScene is always allowed — the last scene leaves the chapter empty (D16)", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: new Response(null, { status: 204 }) });
    const { result } = renderHook(() => useDeleteScene("n1"), { wrapper });
    await result.current.mutateAsync({ sceneId: "s11", chapterId: "c1" });
    expect(api.DELETE).toHaveBeenCalledWith("/api/writing/scenes/{scene_id}", {
      params: { path: { scene_id: "s11" } },
    });
    expect(invalidated).toContainEqual(["scenes", "c1"]);
    expect(invalidated).toContainEqual(["chapters", "n1"]);
    expect(invalidated).toContainEqual(["activity"]);
  });

  it("a refused create throws with its status and asks for nothing", async () => {
    api.POST.mockResolvedValue(refusal(503));
    const { result } = renderHook(() => useCreateChapter("n1"), { wrapper });
    await expect(result.current.mutateAsync()).rejects.toMatchObject({ status: 503 });
    expect(invalidated).toEqual([]);
  });

  it("a refused delete asks for nothing — the rows it would change did not change", async () => {
    api.DELETE.mockResolvedValue(refusal(404));
    const { result } = renderHook(() => useDeleteScene("n1"), { wrapper });
    await expect(result.current.mutateAsync({ sceneId: "s11", chapterId: "c1" })).rejects.toMatchObject({
      status: 404,
    });
    expect(invalidated).toEqual([]);
    expect(removed).toEqual([]);
  });
});

describe("the reorder mutations — the whole set or a 409 naming the stored ids", () => {
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  let invalidated: (readonly unknown[])[];

  beforeEach(() => {
    invalidated = [];
    vi.spyOn(queryClient, "invalidateQueries").mockImplementation((filters?: { queryKey?: readonly unknown[] }) => {
      invalidated.push(filters?.queryKey ?? []);
      return Promise.resolve();
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("chapter order PUTs the whole rail; success asks the novel's timestamp, never the ordered list", async () => {
    api.PUT.mockResolvedValue({ data: undefined, response: new Response(null, { status: 204 }) });
    const { result } = renderHook(() => useReorderChapters("n1"), { wrapper });
    await result.current.mutateAsync(["c2", "c1"]);
    expect(api.PUT).toHaveBeenCalledWith("/api/writing/novels/{novel_id}/chapter-order", {
      params: { path: { novel_id: "n1" } },
      body: { chapter_ids: ["c2", "c1"] },
    });
    expect(invalidated).toContainEqual(["novels"]);
    expect(invalidated).toContainEqual(["activity"]);
    // The optimistic order is what the 204 acknowledged — a chapters refetch
    // mid-unsaved-body is the state the save-side rule guards against.
    expect(invalidated).not.toContainEqual(["chapters", "n1"]);
  });

  it("scene order PUTs the whole chapter under its own door", async () => {
    api.PUT.mockResolvedValue({ data: undefined, response: new Response(null, { status: 204 }) });
    const { result } = renderHook(() => useReorderScenes("n1"), { wrapper });
    await result.current.mutateAsync({ chapterId: "c1", ids: ["s12", "s11"] });
    expect(api.PUT).toHaveBeenCalledWith("/api/writing/chapters/{chapter_id}/scene-order", {
      params: { path: { chapter_id: "c1" } },
      body: { ids: ["s12", "s11"] },
    });
    expect(invalidated).toContainEqual(["novels"]);
    expect(invalidated).not.toContainEqual(["scenes", "c1"]);
  });

  it("a 409 carries the stored ids — the arrangement the client reverts to", async () => {
    api.PUT.mockResolvedValue({
      data: undefined,
      error: { detail: { code: "order_mismatch", chapter_ids: ["c1", "c2", "c3"] } },
      response: new Response(null, { status: 409 }),
    });
    const { result } = renderHook(() => useReorderChapters("n1"), { wrapper });
    await expect(result.current.mutateAsync(["c2", "c1"])).rejects.toMatchObject({
      status: 409,
      storedIds: ["c1", "c2", "c3"],
    });
    expect(invalidated).toEqual([]);
  });

  it("a scene 409 carries scene_ids the same way", async () => {
    api.PUT.mockResolvedValue({
      data: undefined,
      error: { detail: { code: "order_mismatch", scene_ids: ["s11", "s12", "s13"] } },
      response: new Response(null, { status: 409 }),
    });
    const { result } = renderHook(() => useReorderScenes("n1"), { wrapper });
    await expect(result.current.mutateAsync({ chapterId: "c1", ids: ["s12", "s11"] })).rejects.toMatchObject({
      status: 409,
      storedIds: ["s11", "s12", "s13"],
    });
  });

  it("another refusal keeps its status and no stored ids — nothing to revert to", async () => {
    api.PUT.mockResolvedValue({ data: undefined, error: undefined, response: new Response(null, { status: 503 }) });
    const { result } = renderHook(() => useReorderChapters("n1"), { wrapper });
    await expect(result.current.mutateAsync(["c2", "c1"])).rejects.toMatchObject({
      status: 503,
      storedIds: null,
    });
    expect(invalidated).toEqual([]);
  });
});
