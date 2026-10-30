// @vitest-environment jsdom
/**
 * The workbench reads the novel and its chapters through Query, and the four
 * cache states keep their names: while nothing has arrived the page asks
 * ("Loading"), a first load that failed is the named outage with a retry, a
 * refresh that failed with chapters on screen is a quiet note beside work
 * that stays, and data is the workbench. The page never claims the book could
 * not be loaded while its text is on screen.
 *
 * The invalidation rides the autosave's one success callback: a settled save
 * asks the chapters key and the novels prefix to refetch; a save that never
 * landed asks nothing, because a refetch would lay the server's old text over
 * the body the autosave holds for its retry.
 *
 * The page stands in a real router (params, search, blocker) — the same
 * wrapper the shell's fallback tests use — and the API client is mocked at
 * its module boundary: the cases here are about what the page says, and the
 * requests are verified by the backend and E2E suites against the real stack.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { t } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

vi.mock("@shell/lib/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

import { client } from "@shell/lib/api/client";

import { NovelPage } from "./NovelPage";
import { NovelsPage } from "./NovelsPage";

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

const CHAPTER_ID = "71bfa163-2c8f-4a6f-9e07-6f5f2c8d1b63";
const CHAPTERS = [
  {
    id: CHAPTER_ID,
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

function refused(): Response {
  return new Response(null, { status: 500 });
}

/** The answers of a book that loads: the shell's locale gate, the novel's
 *  row, the chapters. */
function loadedAnswer(path: string): unknown {
  switch (path) {
    case "/api/settings":
      return { data: { locale: null }, response: ok() };
    case "/api/writing/novels/{novel_id}":
      return { data: NOVEL, response: ok() };
    case "/api/writing/novels/{novel_id}/chapters":
      return { data: CHAPTERS, response: ok() };
    default:
      throw new Error(`unexpected GET ${path}`);
  }
}

function mockLoaded(): void {
  api.GET.mockImplementation(async (path: string) => loadedAnswer(path));
}

// jsdom lays out nothing: Element geometry reports zeros, but Range geometry
// is simply missing — and ProseMirror reads Range rects whenever it scrolls
// a selection into view (after typing, after focus). Hand it the same zeros
// the elements already claim, so "nothing to scroll" is the only answer.
const zeroRect = { top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0 } as DOMRect;
Range.prototype.getClientRects = function (): DOMRectList {
  return [zeroRect] as unknown as DOMRectList;
};
Range.prototype.getBoundingClientRect = () => zeroRect;

// The workspace route as the page addresses it (`from: "/novels/$id"`), and
// the shelf behind the index — both components direct, no lazy chunk to wait
// for: the router is the page's context, not the subject.
const novelRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$id",
  component: NovelPage,
});
const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: NovelsPage,
});

function renderAt(path: string): void {
  const router = createRouter({
    routeTree: rootRoute.addChildren([homeRoute, novelRoute]),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

/** The mounted editor, once TipTap has put it in the DOM. */
async function editorElement(): Promise<HTMLElement> {
  return waitFor(() => {
    const editable = document.querySelector<HTMLElement>(".ProseMirror");
    expect(editable).not.toBeNull();
    return editable as HTMLElement;
  });
}

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
});

describe("the workbench's four cache states", () => {
  it("names a failed refresh quietly and keeps the work on screen", { timeout: 10_000 }, async () => {
    mockLoaded();
    renderAt(`/novels/${NOVEL_ID}`);
    await editorElement();

    // The refresh is refused — the same read that just answered, not the
    // first load.
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        return { data: undefined, response: refused() };
      }
      return loadedAnswer(path);
    });
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: ["chapters", NOVEL_ID] });
    });

    // The quiet note names the refresh; the workbench stays exactly as it
    // was — editor and rail keep their places, and the page does not claim
    // the book could not be loaded while its text is on screen.
    expect(await screen.findByText(t("chapters.refreshFailed"))).toBeTruthy();
    expect(screen.queryByText(t("chapters.errorLoad"))).toBeNull();
    expect(document.querySelector(".ProseMirror")).not.toBeNull();
    expect(screen.getByRole("button", { name: t("chapters.new") })).toBeTruthy();

    // The note's way back is the same one press: the ask is made again, and
    // the note leaves once it answers.
    mockLoaded();
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await user.click(screen.getByRole("button", { name: t("chapters.retry") }));
    await waitFor(() => expect(screen.queryByText(t("chapters.refreshFailed"))).toBeNull());
    expect(screen.queryByText(t("chapters.errorLoad"))).toBeNull();
    expect(document.querySelector(".ProseMirror")).not.toBeNull();
  });

  it("names an outage when the novel row fails its first load, though the chapters answered", { timeout: 10_000 }, async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels/{novel_id}") {
        return { data: undefined, response: refused() };
      }
      return loadedAnswer(path);
    });
    renderAt(`/novels/${NOVEL_ID}`);

    // The novel row has never arrived, so nothing of the book is on screen:
    // this is the named outage, not a refresh that never happened — and no
    // empty heading claims a book the page cannot name.
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe(t("chapters.errorLoad"));
    expect(screen.queryByText(t("chapters.refreshFailed"))).toBeNull();
    expect(screen.queryByRole("heading")).toBeNull();
    // The empty-rail copy is a loaded book's truth, not a missing one's.
    expect(screen.queryByRole("button", { name: t("chapters.new") })).toBeNull();
  });

  it("names an outage when the chapters fail their first load, though the novel answered", { timeout: 10_000 }, async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        return { data: undefined, response: refused() };
      }
      return loadedAnswer(path);
    });
    renderAt(`/novels/${NOVEL_ID}`);

    // The list has never arrived — the rail would be an empty book's clothes:
    // the outage is named where the retry is one press away.
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe(t("chapters.errorLoad"));
    expect(screen.queryByText(t("chapters.refreshFailed"))).toBeNull();
    expect(screen.queryByRole("button", { name: t("chapters.new") })).toBeNull();
  });
});

describe("the save's invalidation", () => {
  it("asks the chapters key and the novels prefix to refetch once a save landed", { timeout: 10_000 }, async () => {
    mockLoaded();
    api.PUT.mockResolvedValue({ response: ok() });
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    (await editorElement()).focus();
    await user.keyboard("Ein Satz.");

    // The autosave settles (the debounce, then the PUT), and only then —
    // `onSaved` fires on success only — the page asks the cache to refetch:
    // the chapter list the rail (and, later, the palette) reads, and the
    // novels prefix, which covers both the row this page reads and the list
    // the shelf's hero reads.
    await waitFor(
      () => {
        expect(invalidate).toHaveBeenCalledWith({ queryKey: ["chapters", NOVEL_ID] });
        expect(invalidate).toHaveBeenCalledWith({ queryKey: ["novels"] });
      },
      { timeout: 4000 },
    );
    invalidate.mockRestore();
  });

  it("a save that did not land invalidates nothing", { timeout: 10_000 }, async () => {
    mockLoaded();
    api.PUT.mockResolvedValue({ response: refused() });
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    (await editorElement()).focus();
    await user.keyboard("Verloren.");

    // The failure is named beside the text…
    await waitFor(
      () => expect(screen.getByRole("alert").textContent).toContain(t("save.failed")),
      { timeout: 5000 },
    );
    // …and nothing was asked again: a refetch here would lay the server's
    // old text over the body the autosave is holding for its retry. The
    // invalidations ride `onSaved`, which a failed write never reaches.
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(invalidate).not.toHaveBeenCalled();
    invalidate.mockRestore();
  });
});

describe("the shelf's first paint", () => {
  it("paints its own shape while it waits, never a blank", { timeout: 10_000 }, async () => {
    // The shell's locale gate and the setup gate answer; the shelf's own ask
    // hangs — the wait this page must survive visibly.
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") return { data: { locale: null }, response: ok() };
      if (path === "/api/setup/status") return { data: { complete: true }, response: ok() };
      return new Promise(() => {});
    });

    renderAt("/");
    // Once the shelf paints at all, it paints its shape: the heading, the
    // named wait, and the skeleton blocks that claim the loaded layout's
    // heights — the answer's arrival moves content, not layout. The hero's
    // repetition of the first row is deliberate (the continue affordance)
    // and keeps its place above the rows it previews.
    expect(await screen.findByRole("heading", { name: t("novels.heading") })).toBeTruthy();
    expect(screen.getByText(t("novels.loading"))).toBeTruthy();
    expect(document.querySelectorAll(".animate-pulse").length).toBeGreaterThanOrEqual(4);
    // The wait is not an outage: nothing claims the shelf failed.
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
