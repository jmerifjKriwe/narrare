// @vitest-environment jsdom
/**
 * The entity list's placeholder patience (the pure part), and the two
 * workspace hooks: a 200 fills the cache under the key the workbench and the
 * palette read; a 404 is kept as the failure it is — an answer that is not ok
 * throws, so the cache holds either the answer or the error, never an empty
 * book dressed up as data. The client is mocked at its module boundary — the
 * requests themselves are the backend's and the E2Es' to verify.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api/client")>();
  return {
    ...actual,
    client: {
      GET: vi.fn(),
      POST: vi.fn(),
      PATCH: vi.fn(),
      PUT: vi.fn(),
      DELETE: vi.fn(),
    },
  };
});

import { client, isModelChange } from "./api/client";
import {
  queryClient,
  sameNovelPlaceholder,
  useActivityQuery,
  useArchiveNovel,
  useChaptersQuery,
  useCreateTimelineEvent,
  useDeleteDocument,
  useDeleteTimelineEvent,
  useDocumentsQuery,
  useNovelQuery,
  useNovelScenes,
  useNovelsQuery,
  usePassageSearch,
  useSourceSearch,
  useTimelineEvents,
  useUpdateTimelineEvent,
  useUploadDocument,
  invalidateChapterScenes,
} from "./query";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

const NOVEL_ID = "6f1c2a52-9d3e-4f6e-8df5-7db9df0f4a52";

const NOVEL = {
  id: NOVEL_ID,
  title: "Das erreichbare Buch",
  author: null,
  blurb: null,
  genre: null,
  language: null,
  created_at: "2026-10-30T09:00:00Z",
  updated_at: "2026-10-30T09:00:00Z",
};

const CHAPTERS = [
  {
    id: "71bfa163-2c8f-4a6f-9e07-6f5f2c8d1b63",
    novel_id: NOVEL_ID,
    title: "",
    body: "Anfang.",
    position: 0,
    scene_count: 0,
    word_count: 0,
    created_at: "2026-10-30T09:00:00Z",
    updated_at: "2026-10-30T09:00:00Z",
  },
];

function ok(): Response {
  return new Response(null, { status: 200 });
}

function notFound(): Response {
  return new Response(null, { status: 404 });
}

/** The provider the app mounts everything under — the one real client, so
 *  the hooks run with the defaults they run with in the app (`retry: false`). */
function wrapper({ children }: { children: ReactNode }) {
  return createElement(QueryClientProvider, { client: queryClient }, children);
}

afterEach(() => {
  queryClient.clear();
  vi.clearAllMocks();
});

describe("useNovelQuery", () => {
  it("fills [\"novels\", id] with the row a 200 carried", async () => {
    api.GET.mockResolvedValue({ data: NOVEL, response: ok() });
    const hook = renderHook(() => useNovelQuery(NOVEL_ID), { wrapper });

    await waitFor(() => expect(hook.result.current.isSuccess).toBe(true));
    expect(hook.result.current.data).toEqual(NOVEL);
    expect(api.GET).toHaveBeenCalledWith("/api/writing/novels/{novel_id}", {
      params: { path: { novel_id: NOVEL_ID } },
    });
    // The key is part of the contract: the shelf's writes invalidate this
    // row through the ["novels"] prefix, and the palette reads the same key.
    expect(queryClient.getQueryState(["novels", NOVEL_ID])?.status).toBe("success");
  });

  it("keeps a 404 as an error, never as an empty book", async () => {
    api.GET.mockResolvedValue({ data: undefined, response: notFound() });
    const hook = renderHook(() => useNovelQuery(NOVEL_ID), { wrapper });

    await waitFor(() => expect(hook.result.current.isError).toBe(true));
    expect(hook.result.current.data).toBeUndefined();
    expect(hook.result.current.error?.message).toContain("404");
  });
});

describe("useNovelsQuery — the shelf's list, the archive toggle a real refetch", () => {
  const ACTIVE = [{ ...NOVEL, title: "Das aktive Buch" }];
  const ARCHIVED = [{ ...NOVEL, id: "archived-row", title: "Das archivierte Buch" }];

  it("the default asks without a parameter and caches under the false key", async () => {
    api.GET.mockResolvedValue({ data: ACTIVE, response: ok() });
    const hook = renderHook(() => useNovelsQuery(), { wrapper });

    await waitFor(() => expect(hook.result.current.isSuccess).toBe(true));
    expect(hook.result.current.data).toEqual(ACTIVE);
    // The default ask keeps its bare shape — include_archived=false is the
    // server's own default, no parameter sent.
    expect(api.GET).toHaveBeenCalledWith("/api/writing/novels");
    expect(queryClient.getQueryState(["novels", { include_archived: false }])?.status).toBe("success");
  });

  it("includeArchived asks the parameter and caches under its own key", async () => {
    api.GET.mockResolvedValue({ data: [...ACTIVE, ...ARCHIVED], response: ok() });
    const hook = renderHook(() => useNovelsQuery(true), { wrapper });

    await waitFor(() => expect(hook.result.current.isSuccess).toBe(true));
    expect(api.GET).toHaveBeenCalledWith("/api/writing/novels", {
      params: { query: { include_archived: true } },
    });
    expect(queryClient.getQueryState(["novels", { include_archived: true }])?.status).toBe("success");
  });

  it("the toggle holds the previous list while the new ask is in flight", async () => {
    // The archive toggle must not flash the skeleton: the shelf keeps the
    // answer it has until the widened (or narrowed) list lands.
    let resolveArchived!: (answer: { data: unknown; response: Response }) => void;
    api.GET.mockImplementation(async (_path: string, init?: { params?: { query?: { include_archived?: boolean } } }) => {
      if (init?.params?.query?.include_archived) {
        return new Promise<{ data: unknown; response: Response }>((resolve) => {
          resolveArchived = resolve;
        });
      }
      return { data: ACTIVE, response: ok() };
    });
    const hook = renderHook(({ archived }: { archived: boolean }) => useNovelsQuery(archived), {
      wrapper,
      initialProps: { archived: false },
    });
    await waitFor(() => expect(hook.result.current.isSuccess).toBe(true));

    hook.rerender({ archived: true });
    await waitFor(() => expect(hook.result.current.isPlaceholderData).toBe(true));
    expect(hook.result.current.data).toEqual(ACTIVE);
    expect(hook.result.current.isPending).toBe(false);

    resolveArchived({ data: [...ACTIVE, ...ARCHIVED], response: ok() });
    await waitFor(() => expect(hook.result.current.isPlaceholderData).toBe(false));
    expect(hook.result.current.data).toEqual([...ACTIVE, ...ARCHIVED]);
  });

  it("the writes' [\"novels\"] prefix invalidation reaches both list keys", async () => {
    api.GET.mockResolvedValue({ data: ACTIVE, response: ok() });
    const off = renderHook(() => useNovelsQuery(false), { wrapper });
    const on = renderHook(() => useNovelsQuery(true), { wrapper });
    await waitFor(() => expect(off.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(on.result.current.isSuccess).toBe(true));

    // Unmounted, the queries hold the invalidated state instead of
    // refetching it away at once — the prefix's reach is what is pinned.
    off.unmount();
    on.unmount();
    await queryClient.invalidateQueries({ queryKey: ["novels"] });
    expect(queryClient.getQueryState(["novels", { include_archived: false }])?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(["novels", { include_archived: true }])?.isInvalidated).toBe(true);
  });
});

describe("useChaptersQuery", () => {
  it("fills [\"chapters\", id] with the list a 200 carried", async () => {
    api.GET.mockResolvedValue({ data: CHAPTERS, response: ok() });
    const hook = renderHook(() => useChaptersQuery(NOVEL_ID), { wrapper });

    await waitFor(() => expect(hook.result.current.isSuccess).toBe(true));
    expect(hook.result.current.data).toEqual(CHAPTERS);
    expect(api.GET).toHaveBeenCalledWith("/api/writing/novels/{novel_id}/chapters", {
      params: { path: { novel_id: NOVEL_ID } },
    });
    expect(queryClient.getQueryState(["chapters", NOVEL_ID])?.status).toBe("success");
  });

  it("keeps a 404 as an error, never as an empty list", async () => {
    api.GET.mockResolvedValue({ data: undefined, response: notFound() });
    const hook = renderHook(() => useChaptersQuery(NOVEL_ID), { wrapper });

    await waitFor(() => expect(hook.result.current.isError).toBe(true));
    expect(hook.result.current.data).toBeUndefined();
    expect(hook.result.current.error?.message).toContain("404");
  });
});

describe("useActivityQuery — the atelier's aggregate, the banner's read", () => {
  const ACTIVITY = {
    points: [
      { date: "2026-11-15", words: 0 },
      { date: "2026-11-16", words: 412 },
    ],
    streak_days: 1,
    weekly_average: 13.7,
    today_words: 412,
    daily_goal_words: 750,
    goal_met: false,
    goal_remaining: 338,
  };

  it("the default ask keeps its bare shape and caches under the days key", async () => {
    api.GET.mockResolvedValue({ data: ACTIVITY, response: ok() });
    const hook = renderHook(() => useActivityQuery(), { wrapper });

    await waitFor(() => expect(hook.result.current.isSuccess).toBe(true));
    expect(hook.result.current.data).toEqual(ACTIVITY);
    // days=30 is the server's own default — the ask sends no parameter,
    // the novels list's bare-shape convention.
    expect(api.GET).toHaveBeenCalledWith("/api/writing/activity");
    expect(queryClient.getQueryState(["activity", { days: 30 }])?.status).toBe("success");
  });

  it("a narrower window asks its parameter and caches under its own key", async () => {
    api.GET.mockResolvedValue({ data: ACTIVITY, response: ok() });
    const hook = renderHook(() => useActivityQuery(7), { wrapper });

    await waitFor(() => expect(hook.result.current.isSuccess).toBe(true));
    expect(api.GET).toHaveBeenCalledWith("/api/writing/activity", {
      params: { query: { days: 7 } },
    });
    expect(queryClient.getQueryState(["activity", { days: 7 }])?.status).toBe("success");
  });

  it("keeps a refusal as an error with its status — never an empty window", async () => {
    api.GET.mockResolvedValue({ data: undefined, response: new Response(null, { status: 503 }) });
    const hook = renderHook(() => useActivityQuery(), { wrapper });

    await waitFor(() => expect(hook.result.current.isError).toBe(true));
    expect(hook.result.current.data).toBeUndefined();
    expect(hook.result.current.error?.message).toContain("503");
  });
});

describe("the shelf's invalidation family — the list and the aggregate move together", () => {
  it("a novel write invalidates the activity key beside the novels prefix", async () => {
    // Both reads stand cached, then unmount — an invalidated query holds
    // its state instead of refetching it away, the prefix-reach pin's shape.
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/activity") {
        return {
          data: { points: [], streak_days: 0, weekly_average: 0, today_words: 0, daily_goal_words: null, goal_met: false, goal_remaining: 0 },
          response: ok(),
        };
      }
      return { data: [], response: ok() };
    });
    const activity = renderHook(() => useActivityQuery(), { wrapper });
    const novels = renderHook(() => useNovelsQuery(), { wrapper });
    await waitFor(() => expect(activity.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(novels.result.current.isSuccess).toBe(true));
    activity.unmount();
    novels.unmount();

    // A shelf write through the family's door: the archive PATCH succeeds.
    api.PATCH.mockResolvedValue({
      data: { ...NOVEL, archived_at: "2026-11-16T08:00:00Z" },
      response: ok(),
    });
    const archive = renderHook(() => useArchiveNovel(), { wrapper });
    await archive.result.current.mutateAsync({ novelId: NOVEL_ID, archived: true });

    // The banner's aggregate is asked again — a chapter write moves it the
    // same way, through the same door (the workspace wave's save hook).
    expect(queryClient.getQueryState(["activity", { days: 30 }])?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(["novels", { include_archived: false }])?.isInvalidated).toBe(true);
  });
});

describe("the shared [\"knowledge\", \"passages\"] family — one cache, one refusal shape", () => {
  /** The 409 the corpus answers when its embeddings are another model's. */
  function mismatch(): { data: undefined; error: { detail: unknown }; response: Response } {
    return {
      data: undefined,
      error: { detail: { code: "embedding-mismatch", stored: "a", found: "b" } },
      response: new Response(null, { status: 409 }),
    };
  }

  it("the dock's door throws the enriched refusal — a cached 409 is the mismatch, never an outage", async () => {
    api.POST.mockResolvedValue(mismatch());
    const dock = renderHook(() => usePassageSearch("Echo"), { wrapper });

    await waitFor(() => expect(dock.result.current.isError).toBe(true));
    // The refusal carries its status and detail — `isModelChange` is the
    // very predicate the sources face keys its mismatch face on.
    expect(isModelChange(dock.result.current.error)).toBe(true);
    expect((dock.result.current.error as { status?: number }).status).toBe(409);
    // The failure is cached under the family key both doors read.
    expect(queryClient.getQueryState(["knowledge", "passages", "Echo"])?.status).toBe("error");

    // The sources door, mounted on the same cached entry, meets the same
    // enriched refusal — whichever door asked, the face names the mismatch.
    dock.unmount();
    const sources = renderHook(() => useSourceSearch("Echo"), { wrapper });
    await waitFor(() => expect(sources.result.current.isError).toBe(true));
    expect(isModelChange(sources.result.current.error)).toBe(true);
  });
});

describe("the document mutations' invalidation family — the archive and the corpus move together", () => {
  it("a settled delete refetches a standing passage query — a deleted document must not survive a same-string resubmit", async () => {
    api.POST.mockResolvedValue({ data: [], response: ok() });
    api.GET.mockResolvedValue({ data: [], response: ok() });
    api.DELETE.mockResolvedValue({ response: new Response(null, { status: 204 }) });
    const passages = renderHook(() => useSourceSearch("Echo"), { wrapper });
    await waitFor(() => expect(passages.result.current.isSuccess).toBe(true));
    const asks = () => api.POST.mock.calls.filter(([path]) => path === "/api/knowledge/search").length;
    expect(asks()).toBe(1);

    const del = renderHook(() => useDeleteDocument(), { wrapper });
    await del.result.current.mutateAsync("d1");
    // The settle invalidates the passages family: the standing same-string
    // query asks the corpus again, so a just-deleted document's chunks are
    // not replayed from the cache.
    await waitFor(() => expect(asks()).toBeGreaterThan(1));
  });

  it("a settled upload invalidates the passages family beside the documents list", async () => {
    api.POST.mockImplementation((path: string) => {
      if (path === "/api/knowledge/documents") {
        return Promise.resolve({ data: [], response: new Response(null, { status: 201 }) });
      }
      return Promise.resolve({ data: [], response: ok() });
    });
    api.GET.mockResolvedValue({ data: [], response: ok() });
    const passages = renderHook(() => useSourceSearch("Echo"), { wrapper });
    const documents = renderHook(() => useDocumentsQuery(), { wrapper });
    await waitFor(() => expect(passages.result.current.isSuccess).toBe(true));
    // Unmounted, the entries hold the invalidated state instead of
    // refetching it away — the prefix-reach pin's shape.
    passages.unmount();
    documents.unmount();

    const upload = renderHook(() => useUploadDocument(), { wrapper });
    await upload.result.current.mutateAsync(new File(["x"], "Neue Quelle.txt", { type: "text/plain" }));
    expect(queryClient.getQueryState(["knowledge", "passages", "Echo"])?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(["knowledge", "documents"])?.isInvalidated).toBe(true);
  });
});

/**
 * The planning read family (W6 Task 3): the timeline's event list under
 * the planning capability's own key, and the novel-wide scene fan-out —
 * one ask per chapter, each cached under the per-chapter key the
 * aggregate save invalidates (`invalidateChapterScenes`, the seam Task
 * 4's drill-in writes through).
 */
describe("the planning reads", () => {
  const EVENT = {
    id: "ev1",
    novel_id: NOVEL_ID,
    chapter_id: null,
    title: "Der Große Bruch",
    description: "",
    position: 1,
    date_label: "2278",
    character_names: ["Maya Chen"],
    created_at: "2026-11-19T10:00:00Z",
    updated_at: "2026-11-19T10:00:00Z",
  };
  const SECOND_CHAPTER = { ...CHAPTERS[0], id: "c2", position: 1 };
  const AGGREGATE_C1 = {
    chapter_id: CHAPTERS[0].id,
    scenes: [],
    version_updated_at: "2026-11-19T10:00:00Z",
  };
  const AGGREGATE_C2 = {
    chapter_id: SECOND_CHAPTER.id,
    scenes: [],
    version_updated_at: "2026-11-19T10:00:00Z",
  };

  it("useTimelineEvents fills [\"planning\",\"timeline\", id] with the list", async () => {
    api.GET.mockResolvedValue({ data: [EVENT], response: ok() });
    const hook = renderHook(() => useTimelineEvents(NOVEL_ID), { wrapper });

    await waitFor(() => expect(hook.result.current.isSuccess).toBe(true));
    expect(hook.result.current.data).toEqual([EVENT]);
    expect(api.GET).toHaveBeenCalledWith("/api/planning/novels/{novel_id}/timeline-events", {
      params: { path: { novel_id: NOVEL_ID } },
    });
    expect(queryClient.getQueryState(["planning", "timeline", NOVEL_ID])?.status).toBe("success");
  });

  it("keeps a 404 as the error it is — never an invented empty timeline", async () => {
    api.GET.mockResolvedValue({ data: undefined, response: notFound() });
    const hook = renderHook(() => useTimelineEvents(NOVEL_ID), { wrapper });

    await waitFor(() => expect(hook.result.current.isError).toBe(true));
    expect(hook.result.current.data).toBeUndefined();
  });

  it("a settled create invalidates the timeline key the page reads", async () => {
    api.GET.mockResolvedValue({ data: [], response: ok() });
    api.POST.mockResolvedValue({ data: EVENT, response: new Response(null, { status: 201 }) });
    const list = renderHook(() => useTimelineEvents(NOVEL_ID), { wrapper });
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true));
    list.unmount();

    const create = renderHook(() => useCreateTimelineEvent(NOVEL_ID), { wrapper });
    await create.result.current.mutateAsync({
      title: "Der Große Bruch",
      description: "",
      chapter_id: null,
      position: 1,
      date_label: "2278",
      character_names: ["Maya Chen"],
    });
    expect(queryClient.getQueryState(["planning", "timeline", NOVEL_ID])?.isInvalidated).toBe(true);
  });

  it("the edit carries only the dirtied fields — a null clears, an absent field stays", async () => {
    api.PUT.mockResolvedValue({ data: EVENT, response: ok() });
    api.GET.mockResolvedValue({ data: [], response: ok() });
    const edit = renderHook(() => useUpdateTimelineEvent(NOVEL_ID), { wrapper });
    await edit.result.current.mutateAsync({
      eventId: "ev1",
      changes: { title: "Der Große Bruch (korrigiert)", chapter_id: null },
    });
    // The client's mirror of the server's model_fields_set contract: only
    // the carried fields reach the wire, so an absent description or
    // position leaves the stored row alone.
    expect(api.PUT).toHaveBeenCalledWith(
      "/api/planning/novels/{novel_id}/timeline-events/{event_id}",
      {
        params: { path: { novel_id: NOVEL_ID, event_id: "ev1" } },
        body: { title: "Der Große Bruch (korrigiert)", chapter_id: null },
      },
    );
  });

  it("a refused 422 carries its detail across the mutation boundary", async () => {
    api.PUT.mockResolvedValue({
      data: undefined,
      error: { detail: "title must not be blank" },
      response: new Response(null, { status: 422 }),
    });
    api.GET.mockResolvedValue({ data: [], response: ok() });
    const edit = renderHook(() => useUpdateTimelineEvent(NOVEL_ID), { wrapper });
    await expect(
      edit.result.current.mutateAsync({ eventId: "ev1", changes: { title: "  " } }),
    ).rejects.toThrow();
    await waitFor(() => expect(edit.result.current.error).not.toBeNull());
    const thrown = edit.result.current.error;
    expect((thrown as { status?: number }).status).toBe(422);
    expect((thrown as { detail?: unknown }).detail).toBe("title must not be blank");
  });

  it("the delete asks the 204 route and settles the list key on failure too", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: new Response(null, { status: 204 }) });
    api.GET.mockResolvedValue({ data: [], response: ok() });
    const list = renderHook(() => useTimelineEvents(NOVEL_ID), { wrapper });
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true));
    list.unmount();

    const remove = renderHook(() => useDeleteTimelineEvent(NOVEL_ID), { wrapper });
    await remove.result.current.mutateAsync("ev1");
    expect(api.DELETE).toHaveBeenCalledWith(
      "/api/planning/novels/{novel_id}/timeline-events/{event_id}",
      { params: { path: { novel_id: NOVEL_ID, event_id: "ev1" } } },
    );
    expect(queryClient.getQueryState(["planning", "timeline", NOVEL_ID])?.isInvalidated).toBe(true);
  });

  it("the scene fan-out asks every chapter in parallel under its own key", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes") {
        return { data: AGGREGATE_C1, response: ok() };
      }
      throw new Error(`unexpected GET: ${path}`);
    });
    const hook = renderHook(() => useNovelScenes([CHAPTERS[0], SECOND_CHAPTER]), { wrapper });

    await waitFor(() => expect(hook.result.current.isSuccess).toBe(true));
    expect(hook.result.current.data).toEqual([AGGREGATE_C1, AGGREGATE_C1]);
    // One ask per chapter, each carrying its own path param — the fan-out
    // the plan pins, never one invented bulk endpoint.
    const asks = api.GET.mock.calls.filter(
      ([path]) => path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
    );
    expect(asks).toHaveLength(2);
    expect(asks[0][1]).toMatchObject({ params: { path: { chapter_id: CHAPTERS[0].id } } });
    expect(asks[1][1]).toMatchObject({ params: { path: { chapter_id: SECOND_CHAPTER.id } } });
    expect(queryClient.getQueryState(["planning", "scenes", CHAPTERS[0].id])?.status).toBe("success");
    expect(queryClient.getQueryState(["planning", "scenes", SECOND_CHAPTER.id])?.status).toBe("success");
  });

  it("a chapter whose aggregate read fails answers the fan-out with an error", async () => {
    api.GET.mockImplementation(async (_path: string, init?: { params?: { path?: { chapter_id?: string } } }) => {
      if (init?.params?.path?.chapter_id === CHAPTERS[0].id) {
        return { data: undefined, response: notFound() };
      }
      return { data: AGGREGATE_C2, response: ok() };
    });
    const hook = renderHook(() => useNovelScenes([CHAPTERS[0], SECOND_CHAPTER]), { wrapper });

    await waitFor(() => expect(hook.result.current.isError).toBe(true));
    expect(hook.result.current.data).toBeUndefined();
  });

  it("invalidateChapterScenes marks exactly its chapter's key, not its siblings'", async () => {
    api.GET.mockResolvedValue({ data: AGGREGATE_C1, response: ok() });
    const hook = renderHook(() => useNovelScenes([CHAPTERS[0], SECOND_CHAPTER]), { wrapper });
    await waitFor(() => expect(hook.result.current.isSuccess).toBe(true));
    hook.unmount();

    invalidateChapterScenes(SECOND_CHAPTER.id);
    expect(queryClient.getQueryState(["planning", "scenes", SECOND_CHAPTER.id])?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(["planning", "scenes", CHAPTERS[0].id])?.isInvalidated).toBe(false);
  });
});

/**
 * The entity list's placeholder patience: the previous answer stays on
 * screen only while the ask is still the same novel's — a narrowed filter
 * must not blank the list it narrows, but a switch to another novel must
 * not carry the previous novel's rows across. Those rows are selectable,
 * with merge, edit and delete offered on them, so showing them for a
 * story they do not belong to is a lie the next click would carry out.
 */
describe("sameNovelPlaceholder", () => {
  const placeholder = sameNovelPlaceholder("novel-1");
  const previous = [{ id: "e1" }];

  it("keeps the previous answer while the novel is the same", () => {
    expect(
      placeholder(previous, { queryKey: ["knowledge", "entities", "novel-1", {}] }),
    ).toBe(previous);
  });

  it("answers undefined when the previous answer was another novel's", () => {
    expect(
      placeholder(previous, { queryKey: ["knowledge", "entities", "novel-2", {}] }),
    ).toBeUndefined();
  });

  it("answers undefined when there is no previous query", () => {
    expect(placeholder(previous, undefined)).toBeUndefined();
  });
});
