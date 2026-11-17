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

vi.mock("./api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

import { client } from "./api/client";
import {
  queryClient,
  sameNovelPlaceholder,
  useActivityQuery,
  useArchiveNovel,
  useChaptersQuery,
  useNovelQuery,
  useNovelsQuery,
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
