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
import { queryClient, sameNovelPlaceholder, useChaptersQuery, useNovelQuery } from "./query";

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
    expect(queryClient.getQueryState(["novels", NOVEL_ID])).not.toBeNull();
  });

  it("keeps a 404 as an error, never as an empty book", async () => {
    api.GET.mockResolvedValue({ data: undefined, response: notFound() });
    const hook = renderHook(() => useNovelQuery(NOVEL_ID), { wrapper });

    await waitFor(() => expect(hook.result.current.isError).toBe(true));
    expect(hook.result.current.data).toBeUndefined();
    expect(hook.result.current.error?.message).toContain("404");
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
    expect(queryClient.getQueryState(["chapters", NOVEL_ID])).not.toBeNull();
  });

  it("keeps a 404 as an error, never as an empty list", async () => {
    api.GET.mockResolvedValue({ data: undefined, response: notFound() });
    const hook = renderHook(() => useChaptersQuery(NOVEL_ID), { wrapper });

    await waitFor(() => expect(hook.result.current.isError).toBe(true));
    expect(hook.result.current.data).toBeUndefined();
    expect(hook.result.current.error?.message).toContain("404");
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
