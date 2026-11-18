// @vitest-environment jsdom
/**
 * The workspace's read seam (W4 Task 11): the pure helpers that turn the
 * chapters list and the per-chapter scene answers into the tree's ordered
 * entries, the last-edited scene the hero door and the active marker share,
 * the tension card's real scene codes and the storyboard's stage label.
 * The figures are the rows' own — never the draft's mock numbers.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
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

import type { FlushOutcome } from "./useAutosave";
import {
  activeSentence,
  formatClock,
  invalidateSceneReads,
  invalidateStructureReads,
  lastEditedEntry,
  movedIds,
  orderedSceneEntries,
  POMODORO_SECONDS,
  promptWithinBound,
  rowsInOrder,
  sceneCodeNumbers,
  sentenceSpans,
  stageTitleKey,
  tensionCodes,
  useChapterScenes,
  useContinuation,
  useCreateChapter,
  useCreateScene,
  useDeleteChapter,
  useDeleteScene,
  useReorderChapters,
  useReorderScenes,
  useSessionWords,
  useStoryboardQuery,
  useUpdateChapter,
  useUpdateScene,
  useZenTimer,
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
    target_words: null,
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

// --- The continuation stream (W4 Task 16) ---------------------------------
//
// The ghost's lifecycle rides the SSE door: fetch is stubbed at the global
// boundary (the typed client buffers — a stream must arrive piece by piece),
// the frames are the kernel's own bytes. The hook owns the phase machine;
// what the ghost renders and what Tab inserts belong to the editor's tests.

/** A stream the test feeds by hand — the wire's timing is the test's own. */
function controlledStream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const stream = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
  });
  const encoder = new TextEncoder();
  return {
    stream,
    push: (text: string) => controller.enqueue(encoder.encode(text)),
    close: () => controller.close(),
  };
}

function sseResponse(stream: ReadableStream<Uint8Array>, status = 200): Response {
  return new Response(stream, { status, headers: { "Content-Type": "text/event-stream" } });
}

const DELTA_A = 'data: {"delta": "Der Nebel hob sich "}\n\n';
const DELTA_B = 'data: {"delta": "vom See."}\n\n';
const DONE = "event: done\ndata: {}\n\n";

describe("promptWithinBound — the client's mirror of the schema's bound", () => {
  it("1 and 2000 raw characters pass, no trim — the chat question's precedent", () => {
    expect(promptWithinBound("X")).toBe(true);
    expect(promptWithinBound("X".repeat(2000))).toBe(true);
    // Whitespace is a character too: the schema does not trim, neither does
    // the mirror (Task 15's no-trim pin).
    expect(promptWithinBound(" ")).toBe(true);
    expect(promptWithinBound(" X ")).toBe(true);
  });

  it("empty and over-long refuse — the 422 the client never lets reach the wire", () => {
    expect(promptWithinBound("")).toBe(false);
    expect(promptWithinBound("X".repeat(2001))).toBe(false);
  });

  it("counts code points, not UTF-16 units — the server's len() is the authority", () => {
    // An astral character (🌊, U+1F30A) is ONE Python code point and TWO
    // UTF-16 units: 2000 of them are 4000 .length units the old mirror
    // refused while the server accepts (test_continuation's astral pin).
    expect(promptWithinBound("🌊".repeat(2000))).toBe(true);
    expect(promptWithinBound("🌊".repeat(2001))).toBe(false);
    // The mixed boundary: 1999 BMP characters + one astral = 2000 code
    // points (2001 UTF-16 units) — within; one more BMP character refuses.
    expect(promptWithinBound("X".repeat(1999) + "🌊")).toBe(true);
    expect(promptWithinBound("X".repeat(2000) + "🌊")).toBe(false);
  });
});

describe("useContinuation — the ghost's lifecycle", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function mount(sceneId: string | null = "s1") {
    return renderHook(({ id }: { id: string | null }) => useContinuation(id), {
      initialProps: { id: sceneId },
    });
  }

  it("streams deltas into the ghost text and rests pending at done", async () => {
    const wire = controlledStream();
    fetchMock.mockResolvedValue(sseResponse(wire.stream));
    const { result } = mount();
    expect(result.current.phase).toBe("idle");

    act(() => result.current.start());
    expect(result.current.phase).toBe("streaming");
    expect(result.current.text).toBe("");
    // The bare continuation: no body at all, the endpoint's own shape.
    expect(fetchMock).toHaveBeenCalledWith("/api/writing/scenes/s1/continue", {
      method: "POST",
      signal: expect.any(AbortSignal),
    });

    await act(async () => wire.push(DELTA_A));
    await waitFor(() => expect(result.current.text).toBe("Der Nebel hob sich "));
    expect(result.current.phase).toBe("streaming");

    await act(async () => wire.push(DELTA_B + DONE));
    await waitFor(() => expect(result.current.phase).toBe("pending"));
    expect(result.current.text).toBe("Der Nebel hob sich vom See.");
    expect(result.current.errorCode).toBeNull();
  });

  it("a carried prompt rides the JSON body — the pill's round-trip", async () => {
    const wire = controlledStream();
    fetchMock.mockResolvedValue(sseResponse(wire.stream));
    const { result } = mount();
    act(() => result.current.start("Spannungsspitze einbauen"));
    expect(fetchMock).toHaveBeenCalledWith("/api/writing/scenes/s1/continue", {
      method: "POST",
      signal: expect.any(AbortSignal),
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: "Spannungsspitze einbauen" }),
    });
    await act(async () => wire.push(DONE));
    // An empty answer is no continuation — the error face, not a blank pill.
    await waitFor(() => expect(result.current.phase).toBe("error"));
    expect(result.current.errorCode).toBe("empty");
  });

  it("the coded error frame names the failure — the ghost never half-stands", async () => {
    const wire = controlledStream();
    fetchMock.mockResolvedValue(sseResponse(wire.stream));
    const { result } = mount();
    act(() => result.current.start());
    await act(async () => wire.push(DELTA_A));
    await act(async () => wire.push('event: error\ndata: {"code": "key-unavailable"}\n\n'));
    await waitFor(() => expect(result.current.phase).toBe("error"));
    expect(result.current.errorCode).toBe("key-unavailable");
    // What arrived stays readable in the state — the face owns the copy.
    expect(result.current.text).toBe("Der Nebel hob sich ");
  });

  it("a JSON refusal before the stream is the error face by status", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 422 }));
    const { result } = mount();
    act(() => result.current.start("X".repeat(2001)));
    await waitFor(() => expect(result.current.phase).toBe("error"));
    expect(result.current.errorCode).toBe("http-422");
  });

  it("a dead connection is the error face, never a silent idle", async () => {
    fetchMock.mockRejectedValue(new TypeError("failed to fetch"));
    const { result } = mount();
    act(() => result.current.start());
    await waitFor(() => expect(result.current.phase).toBe("error"));
    expect(result.current.errorCode).toBe("network");
  });

  it("a silent close without a terminal frame is a failure — the router's own rule", async () => {
    const wire = controlledStream();
    fetchMock.mockResolvedValue(sseResponse(wire.stream));
    const { result } = mount();
    act(() => result.current.start());
    await act(async () => {
      wire.push(DELTA_A);
      wire.close();
    });
    await waitFor(() => expect(result.current.phase).toBe("error"));
    expect(result.current.errorCode).toBe("interrupted");
  });

  it("dismiss aborts the stream and clears the ghost — no error face for a chosen stop", async () => {
    const wire = controlledStream();
    fetchMock.mockResolvedValue(sseResponse(wire.stream));
    const { result } = mount();
    act(() => result.current.start());
    await act(async () => wire.push(DELTA_A));
    await waitFor(() => expect(result.current.text).not.toBe(""));

    act(() => result.current.dismiss());
    expect(result.current.phase).toBe("idle");
    expect(result.current.text).toBe("");
    // The wire keeps moving after the stop — the retired loop must not answer.
    await act(async () => {
      wire.push(DELTA_B + DONE);
      wire.close();
    });
    expect(result.current.phase).toBe("idle");
    expect(result.current.text).toBe("");
  });

  it("dismiss clears the error face too — Verwerfen", async () => {
    fetchMock.mockRejectedValue(new TypeError("failed to fetch"));
    const { result } = mount();
    act(() => result.current.start());
    await waitFor(() => expect(result.current.phase).toBe("error"));
    act(() => result.current.dismiss());
    expect(result.current.phase).toBe("idle");
    expect(result.current.errorCode).toBeNull();
  });

  it("retry re-runs the very ask — the last prompt rides again", async () => {
    const first = controlledStream();
    const second = controlledStream();
    fetchMock.mockResolvedValueOnce(sseResponse(first.stream)).mockResolvedValueOnce(sseResponse(second.stream));
    const { result } = mount();
    act(() => result.current.start("Dialog vertiefen"));
    await act(async () => first.push('event: error\ndata: {"code": "unknown"}\n\n'));
    await waitFor(() => expect(result.current.phase).toBe("error"));

    act(() => result.current.retry());
    expect(result.current.phase).toBe("streaming");
    expect(fetchMock).toHaveBeenLastCalledWith("/api/writing/scenes/s1/continue", {
      method: "POST",
      signal: expect.any(AbortSignal),
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: "Dialog vertiefen" }),
    });
    await act(async () => second.push(DELTA_A + DONE));
    await waitFor(() => expect(result.current.phase).toBe("pending"));
  });

  it("a new start replaces a standing stream — one ghost at a time", async () => {
    const first = controlledStream();
    const second = controlledStream();
    fetchMock.mockResolvedValueOnce(sseResponse(first.stream)).mockResolvedValueOnce(sseResponse(second.stream));
    const { result } = mount();
    act(() => result.current.start());
    await act(async () => first.push(DELTA_A));
    await waitFor(() => expect(result.current.text).toBe("Der Nebel hob sich "));

    act(() => result.current.start("Details ausschmücken"));
    expect(result.current.text).toBe("");
    await act(async () => {
      first.push(DELTA_B + DONE);
      second.push(DELTA_B + DONE);
    });
    await waitFor(() => expect(result.current.phase).toBe("pending"));
    // Only the second stream's words stand — the retired one never answered.
    expect(result.current.text).toBe("vom See.");
  });

  it("a scene switch retires the ghost — it belongs to the tail it was asked for", async () => {
    const wire = controlledStream();
    fetchMock.mockResolvedValue(sseResponse(wire.stream));
    const { result, rerender } = mount("s1");
    act(() => result.current.start());
    await act(async () => wire.push(DELTA_A + DONE));
    await waitFor(() => expect(result.current.phase).toBe("pending"));

    rerender({ id: "s2" });
    await waitFor(() => expect(result.current.phase).toBe("idle"));
    expect(result.current.text).toBe("");
  });

  it("no scene, no ask — the empty faces carry no continuation", () => {
    const { result } = mount(null);
    act(() => result.current.start());
    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.phase).toBe("idle");
  });

  it("the scene id rides encoded — one path segment, whatever the id carries", async () => {
    const wire = controlledStream();
    fetchMock.mockResolvedValue(sseResponse(wire.stream));
    const { result } = mount("a/b?c#d");
    act(() => result.current.start());
    expect(fetchMock).toHaveBeenCalledWith("/api/writing/scenes/a%2Fb%3Fc%23d/continue", {
      method: "POST",
      signal: expect.any(AbortSignal),
    });
  });

  it("unmount aborts the stream — the audit records the interruption server-side", async () => {
    const wire = controlledStream();
    fetchMock.mockResolvedValue(sseResponse(wire.stream));
    const { result, unmount } = mount();
    act(() => result.current.start());
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const signal = fetchMock.mock.calls[0][1].signal as AbortSignal;
    expect(signal.aborted).toBe(false);
    unmount();
    expect(signal.aborted).toBe(true);
  });
});

// --- The save seam: flush first, the writer saves before the ask ----------
//
// The server continues the SAVED body — the page hands its autosave's flush
// over, and every start and retry settles the draft before the wire (the
// leave guard's flush-first rule, the ask's own door). A failed flush sends
// nothing; the autosave's failure face stands instead.

describe("useContinuation's save seam — flush before the wire", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  /** A flush the test settles by hand — the draft's timing is the test's. */
  function heldFlush() {
    let settle!: (outcome: FlushOutcome) => void;
    const flush = vi.fn(
      () =>
        new Promise<FlushOutcome>((resolve) => {
          settle = resolve;
        }),
    );
    return { flush, settle: (outcome: FlushOutcome) => settle(outcome) };
  }

  it("a pending body's flush lands BEFORE the continue request", async () => {
    const order: string[] = [];
    const flush = vi.fn(async () => {
      order.push("flush");
      return "saved" as const;
    });
    const wire = controlledStream();
    fetchMock.mockImplementation(async () => {
      order.push("continue");
      return sseResponse(wire.stream);
    });
    const { result } = renderHook(() => useContinuation("s1", flush));
    act(() => result.current.start("Spannungsspitze einbauen"));
    // The ask waits for the save — nothing on the wire yet.
    expect(fetchMock).not.toHaveBeenCalled();
    await waitFor(() => expect(result.current.phase).toBe("streaming"));
    expect(order).toEqual(["flush", "continue"]);
    expect(fetchMock).toHaveBeenCalledWith("/api/writing/scenes/s1/continue", {
      method: "POST",
      signal: expect.any(AbortSignal),
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: "Spannungsspitze einbauen" }),
    });
  });

  it("a failed flush sends nothing — the autosave's failure face answers instead", async () => {
    const flush = vi.fn(async () => "failed" as const);
    const { result } = renderHook(() => useContinuation("s1", flush));
    act(() => result.current.start());
    await waitFor(() => expect(flush).toHaveBeenCalled());
    // Give the retired ask every chance to (wrongly) fire.
    await act(async () => {});
    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.phase).toBe("idle");
    expect(result.current.errorCode).toBeNull();
  });

  it("retry flushes too — the very ask, save-first again", async () => {
    const order: string[] = [];
    const flush = vi.fn(async () => {
      order.push("flush");
      return "clean" as const;
    });
    const first = controlledStream();
    const second = controlledStream();
    fetchMock
      .mockImplementationOnce(async () => {
        order.push("continue");
        return sseResponse(first.stream);
      })
      .mockImplementationOnce(async () => {
        order.push("continue");
        return sseResponse(second.stream);
      });
    const { result } = renderHook(() => useContinuation("s1", flush));
    act(() => result.current.start("Dialog vertiefen"));
    await waitFor(() => expect(result.current.phase).toBe("streaming"));
    await act(async () => first.push('event: error\ndata: {"code": "unknown"}\n\n'));
    await waitFor(() => expect(result.current.phase).toBe("error"));

    act(() => result.current.retry());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(order).toEqual(["flush", "continue", "flush", "continue"]);
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/writing/scenes/s1/continue",
      expect.objectContaining({ body: JSON.stringify({ prompt: "Dialog vertiefen" }) }),
    );
  });

  it("a clean flush keeps today's ask — the bare continuation, byte for byte", async () => {
    const flush = vi.fn(async () => "clean" as const);
    const wire = controlledStream();
    fetchMock.mockResolvedValue(sseResponse(wire.stream));
    const { result } = renderHook(() => useContinuation("s1", flush));
    act(() => result.current.start());
    await waitFor(() => expect(result.current.phase).toBe("streaming"));
    expect(fetchMock).toHaveBeenCalledWith("/api/writing/scenes/s1/continue", {
      method: "POST",
      signal: expect.any(AbortSignal),
    });
    await act(async () => wire.push(DELTA_A + DONE));
    await waitFor(() => expect(result.current.phase).toBe("pending"));
    expect(result.current.text).toBe("Der Nebel hob sich ");
  });

  it("a dismissal during the flush retires the ask — typing wins", async () => {
    const { flush, settle } = heldFlush();
    const { result } = renderHook(() => useContinuation("s1", flush));
    act(() => result.current.start());
    act(() => result.current.dismiss());
    await act(async () => settle("saved"));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.phase).toBe("idle");
  });

  it("a scene switch during the flush retires the ask — the ghost belongs to its tail", async () => {
    const { flush, settle } = heldFlush();
    const { result, rerender } = renderHook(({ id }: { id: string }) => useContinuation(id, flush), {
      initialProps: { id: "s1" },
    });
    act(() => result.current.start());
    rerender({ id: "s2" });
    await act(async () => settle("saved"));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.phase).toBe("idle");
  });
});

// --- The zen seam (W4 Task 18) ---------------------------------------------
//
// The focus presets' sentence geometry, the session-only pomodoro and the
// session word delta — the frontend-real pieces of the zen draft (D6). The
// timer keeps nothing: no storage write is its contract (design §12), and
// the counters' today half reads the activity aggregate at the page, not
// here.

describe("sentenceSpans — the sentence focus's geometry", () => {
  it("splits on terminal punctuation, the whitespace between belongs to no sentence", () => {
    expect(sentenceSpans("Eins zwei. Drei vier. Fünf.")).toEqual([
      [0, 10],
      [11, 21],
      [22, 27],
    ]);
  });

  it("keeps the closing quotes with the sentence they close — the German face", () => {
    const text = "»Quelle triangulieren«, befahl ich. „Gut“, sagte sie.";
    const spans = sentenceSpans(text);
    expect(spans).toHaveLength(2);
    expect(text.slice(spans[0][0], spans[0][1])).toBe("»Quelle triangulieren«, befahl ich.");
    expect(text.slice(spans[1][0], spans[1][1])).toBe("„Gut“, sagte sie.");
  });

  it("a run of terminals and an ellipsis end one sentence, not several", () => {
    expect(sentenceSpans("Wirklich?! Ja… Nein.")).toEqual([
      [0, 10],
      [11, 14],
      [15, 20],
    ]);
  });

  it("text without a terminal is one sentence — the whole span", () => {
    expect(sentenceSpans("ein langer Satz ohne Punkt")).toEqual([[0, 26]]);
  });

  it("empty and whitespace-only text carry no sentence", () => {
    expect(sentenceSpans("")).toEqual([]);
    expect(sentenceSpans("   \n  ")).toEqual([]);
  });

  it("a hard break's newline is whitespace — the sentence reads across it", () => {
    expect(sentenceSpans("Eins\nzwei. Drei.")).toEqual([
      [0, 10],
      [11, 16],
    ]);
  });
});

describe("activeSentence — the caret's sentence, honestly", () => {
  const text = "Eins zwei. Drei vier. Fünf.";

  it("an offset inside a sentence keeps that sentence", () => {
    expect(activeSentence(text, 3)).toEqual([0, 10]);
    expect(activeSentence(text, 15)).toEqual([11, 21]);
  });

  it("the boundary after the terminal keeps the sentence just ended", () => {
    expect(activeSentence(text, 10)).toEqual([0, 10]);
  });

  it("the whitespace between sentences keeps the previous — the writer just finished it", () => {
    expect(activeSentence(text, 10.5)).toEqual([0, 10]);
  });

  it("no text, no sentence — null, never an invented span", () => {
    expect(activeSentence("", 0)).toBeNull();
  });
});

describe("formatClock — the pomodoro's face", () => {
  it("minutes and seconds, two digits each", () => {
    expect(formatClock(POMODORO_SECONDS)).toBe("25:00");
    expect(formatClock(1122)).toBe("18:42");
    expect(formatClock(0)).toBe("00:00");
    expect(formatClock(61)).toBe("01:01");
  });
});

describe("useZenTimer — the session-only pomodoro", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("starts full and running — the draft's timer is already on", () => {
    const { result } = renderHook(() => useZenTimer());
    expect(result.current.remaining).toBe(POMODORO_SECONDS);
    expect(result.current.running).toBe(true);
    expect(result.current.done).toBe(false);
  });

  it("counts down one second at a time", () => {
    const { result } = renderHook(() => useZenTimer());
    act(() => vi.advanceTimersByTime(61_000));
    expect(result.current.remaining).toBe(POMODORO_SECONDS - 61);
  });

  // The Codacy drift fix: the remaining time reads a wall-clock deadline,
  // never the tick count. A throttled background tab (or a machine sleep)
  // fires fewer ticks than seconds passed — counting callbacks would
  // stretch the session past its span. The tick only re-renders the time
  // the deadline already names.
  it("a throttled tick cannot stretch the session — the remaining time tracks the wall clock", () => {
    const intervals = vi.spyOn(window, "setInterval");
    const { result } = renderHook(() => useZenTimer());
    const tick = intervals.mock.calls.find((call) => call[1] === 1000)?.[0] as () => void;
    // Sixty wall-clock seconds pass, but only ONE tick fires.
    act(() => {
      vi.setSystemTime(Date.now() + 60_000);
      tick();
    });
    expect(result.current.remaining).toBe(POMODORO_SECONDS - 60);
    intervals.mockRestore();
  });

  it("a burst of ticks without wall time spends nothing — the deadline is the authority", () => {
    const intervals = vi.spyOn(window, "setInterval");
    const { result } = renderHook(() => useZenTimer());
    const tick = intervals.mock.calls.find((call) => call[1] === 1000)?.[0] as () => void;
    act(() => {
      tick();
      tick();
      tick();
      tick();
      tick();
    });
    expect(result.current.remaining).toBe(POMODORO_SECONDS);
    intervals.mockRestore();
  });

  it("pause holds the span across a clock jump — resume carries the held remainder", () => {
    const { result } = renderHook(() => useZenTimer());
    act(() => vi.advanceTimersByTime(10_000));
    act(() => result.current.toggle());
    // The machine sleeps an hour while the clock is held — the held span
    // is the remainder at pause, not a deadline the sleep runs past.
    act(() => vi.setSystemTime(Date.now() + 3_600_000));
    expect(result.current.remaining).toBe(POMODORO_SECONDS - 10);
    act(() => result.current.toggle());
    act(() => vi.advanceTimersByTime(5_000));
    expect(result.current.remaining).toBe(POMODORO_SECONDS - 15);
  });

  it("a sleep past the deadline expires honestly — the first tick after waking rests at zero", () => {
    const intervals = vi.spyOn(window, "setInterval");
    const { result } = renderHook(() => useZenTimer());
    const tick = intervals.mock.calls.find((call) => call[1] === 1000)?.[0] as () => void;
    act(() => {
      vi.setSystemTime(Date.now() + POMODORO_SECONDS * 1000 + 60_000);
      tick();
    });
    expect(result.current.remaining).toBe(0);
    expect(result.current.done).toBe(true);
    expect(result.current.running).toBe(false);
    // Further ticks keep the rest — never negative, never a restart.
    act(() => tick());
    expect(result.current.remaining).toBe(0);
    intervals.mockRestore();
  });

  it("pause holds the clock, resume carries it on", () => {
    const { result } = renderHook(() => useZenTimer());
    act(() => vi.advanceTimersByTime(10_000));
    act(() => result.current.toggle());
    expect(result.current.running).toBe(false);
    act(() => vi.advanceTimersByTime(30_000));
    expect(result.current.remaining).toBe(POMODORO_SECONDS - 10);
    act(() => result.current.toggle());
    act(() => vi.advanceTimersByTime(5_000));
    expect(result.current.remaining).toBe(POMODORO_SECONDS - 15);
  });

  it("reset returns the full span, running again", () => {
    const { result } = renderHook(() => useZenTimer());
    act(() => vi.advanceTimersByTime(60_000));
    act(() => result.current.toggle());
    act(() => result.current.reset());
    expect(result.current.remaining).toBe(POMODORO_SECONDS);
    expect(result.current.running).toBe(true);
  });

  it("stops at zero — done, never negative; the toggle starts a fresh span", () => {
    const { result } = renderHook(() => useZenTimer());
    act(() => vi.advanceTimersByTime(POMODORO_SECONDS * 1000 + 5_000));
    expect(result.current.remaining).toBe(0);
    expect(result.current.done).toBe(true);
    expect(result.current.running).toBe(false);
    act(() => result.current.toggle());
    expect(result.current.remaining).toBe(POMODORO_SECONDS);
    expect(result.current.running).toBe(true);
  });

  it("writes nothing to storage — the session is the whole lifetime (design §12)", () => {
    const local = vi.spyOn(Storage.prototype, "setItem");
    const session = vi.spyOn(window, "sessionStorage", "get");
    const { result } = renderHook(() => useZenTimer());
    act(() => vi.advanceTimersByTime(120_000));
    act(() => result.current.toggle());
    act(() => result.current.reset());
    expect(local).not.toHaveBeenCalled();
    expect(session).not.toHaveBeenCalled();
    local.mockRestore();
    session.mockRestore();
  });
});

describe("useSessionWords — the live delta since zen entry", () => {
  it("starts at zero — the entry body is the baseline, not a claim", () => {
    const { result } = renderHook(() => useSessionWords("Eins zwei drei."));
    expect(result.current.words).toBe(0);
  });

  it("counts the net words the session adds", () => {
    const { result } = renderHook(() => useSessionWords("Eins zwei."));
    act(() => result.current.track("Eins zwei. Drei vier."));
    expect(result.current.words).toBe(2);
    act(() => result.current.track("Eins zwei. Drei vier. Fünf."));
    expect(result.current.words).toBe(3);
  });

  it("a removal is honest — the delta goes negative, never hidden", () => {
    const { result } = renderHook(() => useSessionWords("Eins zwei drei."));
    act(() => result.current.track("Eins."));
    expect(result.current.words).toBe(-2);
  });

  it("the shared whitespace rule counts — the server's own figure", () => {
    const { result } = renderHook(() => useSessionWords(""));
    act(() => result.current.track("  eins\u00a0zwei  "));
    expect(result.current.words).toBe(2);
  });
});
