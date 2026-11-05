// @vitest-environment jsdom
/**
 * The workbench reads the novel and its chapters through Query, and the four
 * cache states keep their names: while nothing has arrived the page asks
 * ("Loading"), a first load that failed is the named outage with a retry, a
 * refresh that failed with chapters on screen is a quiet note beside work
 * that stays, and data is the workbench. The page never claims the book could
 * not be loaded while its text is on screen.
 *
 * The selection is URL state: the rail writes `?chapter=`, an arrival without
 * one falls back to the last chapter written in and writes nothing. Every
 * navigation while text is unsaved passes the flush gate — the cases the
 * browser-level suite cannot reach (the leave dialog's two answers, a
 * search-only switch meeting a refused write) are pinned here.
 *
 * The invalidation rides the autosave's one success callback, and the saved
 * body reaches the cache before the ask: a settled save patches its text
 * into the chapters key, then asks the key and the novels prefix to
 * refetch; a save that never landed asks nothing, because a refetch would
 * lay the server's old text over the body the autosave holds for its retry.
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
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { clearAnnouncements } from "@shell/lib/announce";
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

import { client, type Chapter } from "@shell/lib/api/client";

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
const SECOND_CHAPTER_ID = "9c4e37a1-5b8d-4c2f-8a16-3e7f9d2c4b05";
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

/** The same book with a second chapter written in later than the first. */
const TWO_CHAPTERS = [
  ...CHAPTERS,
  {
    id: SECOND_CHAPTER_ID,
    novel_id: NOVEL_ID,
    title: "",
    body: "",
    position: 1,
    created_at: "2026-10-30T09:00:00Z",
    updated_at: "2026-10-30T09:01:00Z",
  },
];

const OTHER_NOVEL_ID = "8e2c3a52-9d3e-4f6e-8df5-7db9df0f4a53";
const OTHER_CHAPTER_ID = "ba11b163-2c8f-4a6f-9e07-6f5f2c8d1b65";
/** The other book's own rows — its last-touched chapter is its only one. */
const OTHER_NOVEL = { ...NOVEL, id: OTHER_NOVEL_ID, title: "Das andere Buch" };
const OTHER_CHAPTERS = [
  {
    id: OTHER_CHAPTER_ID,
    novel_id: OTHER_NOVEL_ID,
    title: "",
    body: "Anderer Anfang.",
    position: 0,
    created_at: "2026-10-30T09:00:00Z",
    updated_at: "2026-10-30T09:30:00Z",
  },
];

/** Two chapters with names of their own. A reorder's witness needs them:
 *  untitled rows are named by their position ("Kapitel n"), so a swapped
 *  rail of unnamed chapters reads exactly like the one it replaced. */
const TWO_NAMED_CHAPTERS = [
  { ...TWO_CHAPTERS[0], title: "Erstes" },
  { ...TWO_CHAPTERS[1], title: "Zweites" },
];

const THIRD_CHAPTER_ID = "b2f8ea7d-4a3b-4c5d-9e2f-8a1b0c3d4e06";
/** Three named chapters: enough room that a second move is its own
 *  arrangement, not the first one undone. */
const THREE_NAMED_CHAPTERS = [
  ...TWO_NAMED_CHAPTERS,
  {
    id: THIRD_CHAPTER_ID,
    novel_id: NOVEL_ID,
    title: "Drittes",
    body: "",
    position: 2,
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

/** The loaded answers with a second chapter in the rail's list. */
function mockTwoChapters(): void {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/writing/novels/{novel_id}/chapters") {
      return { data: TWO_CHAPTERS, response: ok() };
    }
    return loadedAnswer(path);
  });
}

/** The loaded answers with the named pair in the rail's list. */
function mockTwoNamedChapters(): void {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/writing/novels/{novel_id}/chapters") {
      return { data: TWO_NAMED_CHAPTERS, response: ok() };
    }
    return loadedAnswer(path);
  });
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

function renderAt(path: string) {
  const router = createRouter({
    routeTree: rootRoute.addChildren([homeRoute, novelRoute]),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

/** The mounted editor, once TipTap has put it in the DOM. */
async function editorElement(): Promise<HTMLElement> {
  return waitFor(() => {
    const editable = document.querySelector<HTMLElement>(".ProseMirror");
    expect(editable).not.toBeNull();
    return editable as HTMLElement;
  });
}

/** Click a rail row by its chapter number: the accessible name is the
 *  title plus the count the shared rule reports for its body. */
function chapterRow(n: number): HTMLElement {
  return screen.getByRole("button", {
    name: new RegExp(`^${t("chapters.defaultTitle", { n })}\\b`),
  });
}

/** The rail's named chapters as DOM positions: where each titled row
 *  sits in the list. `[1, 0]` is a reversed pair — "Zweites" is the
 *  list's first. (Named rows, because a position-derived label moves
 *  with the swap it names.) */
function railOrder(): number[] {
  const rail = screen.getByRole("complementary");
  return ["Erstes", "Zweites"].map((name) =>
    [...rail.querySelectorAll<HTMLButtonElement>("button")].findIndex((button) =>
      (button.getAttribute("aria-label") ?? "").startsWith(`${name} `),
    ),
  );
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
    // the book could not be loaded while its text is on screen. The note is
    // background speech (`role="status"`), not an alert: the work on screen
    // is unharmed, and a screen reader must still hear that the refresh it
    // asked for did not arrive.
    const note = await screen.findByText(t("chapters.refreshFailed"));
    expect(note.getAttribute("role")).toBe("status");
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
    // The Notice's retry action shares the alert's text — the announcement
    // carries the fix, so the message is asserted as a part, not the whole.
    expect(alert.textContent).toContain(t("chapters.errorLoad"));
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
    expect(alert.textContent).toContain(t("chapters.errorLoad"));
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

  it("patches the saved body into the chapters cache before the refetch can fail", { timeout: 10_000 }, async () => {
    // The read that answers first, then silence: the refetch a settled save
    // asks for never comes back, so the cache's own content is what a later
    // switch would remount.
    let chapterReads = 0;
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") return { data: { locale: null }, response: ok() };
      if (path === "/api/writing/novels/{novel_id}") return { data: NOVEL, response: ok() };
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        chapterReads += 1;
        if (chapterReads === 1) return { data: CHAPTERS, response: ok() };
        return new Promise(() => {});
      }
      throw new Error(`unexpected GET ${path}`);
    });
    api.PUT.mockResolvedValue({ response: ok() });
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    (await editorElement()).focus();
    await user.keyboard(" Ein Satz.");

    // The save settled and its ask is still hanging, yet the cache already
    // holds the saved text: the patch rides `onSaved` ahead of the
    // invalidation, so a refetch that never answers cannot remount the
    // pre-save row — with the freshness its updated_at stands for — over
    // the writer's words.
    await waitFor(
      () => {
        const rows = queryClient.getQueryData<Array<Chapter>>(["chapters", NOVEL_ID]);
        const saved = rows?.find((row) => row.id === CHAPTER_ID);
        expect(saved?.body).toContain("Ein Satz.");
        expect(saved?.updated_at).not.toBe(CHAPTERS[0].updated_at);
      },
      { timeout: 4000 },
    );
  });
});

describe("the gate every navigation passes", () => {
  /** The workbench on the chapter last written in — the fallback's choice,
   *  the second row — with a refused write outstanding. The gate's ask is
   *  the shell's dialog now: these tests answer it through its buttons, the
   *  way the user does. The router comes back for the programmatic second
   *  asks no user event can produce (a pointer press dismisses the ask
   *  first — that is the dismissal, and the click that follows asks anew). */
  async function renderWithFailedSave() {
    mockTwoChapters();
    api.PUT.mockResolvedValue({ response: refused() });
    const router = renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    (await editorElement()).focus();
    await user.keyboard("Bleibt hier.");
    await screen.findByText(t("save.failed"), undefined, { timeout: 4000 });
    return { user, router };
  }

  it("asks before a switch drops a refused body, and a dismissed ask keeps it", { timeout: 10_000 }, async () => {
    const { user } = await renderWithFailedSave();

    // The switch to the first chapter is a navigation like any other, so
    // the gate runs its flush — refused here — and asks. The ask is
    // dismissed ("Bleiben"): the selection stays, and the refused body
    // with it.
    await user.click(chapterRow(1));
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("button", { name: t("save.leaveStay") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(chapterRow(2).getAttribute("aria-current")).toBe("true");
    expect(document.querySelector(".ProseMirror")?.textContent).toContain("Bleibt hier.");
  });

  it("an accepted ask discards the refused body and completes the switch", { timeout: 10_000 }, async () => {
    const { user } = await renderWithFailedSave();

    // The same question answered with "Trotzdem wechseln": the user chose
    // to leave the refused body behind, so the switch completes — the
    // first chapter's text is what the editor holds, and the refused words
    // are nowhere.
    await user.click(chapterRow(1));
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("button", { name: t("save.leaveGo") }));
    await waitFor(() => expect(chapterRow(1).getAttribute("aria-current")).toBe("true"));
    expect(document.querySelector(".ProseMirror")?.textContent).toBe("Anfang.");
  });

  it("the ask disarms the workbench: a second ask cannot strand the first", { timeout: 10_000 }, async () => {
    const { user, router } = await renderWithFailedSave();

    await user.click(chapterRow(1));
    const dialog = await screen.findByRole("dialog");

    // F9 belongs to the dialog while it stands: the rail it would hide is
    // still in the document (aria-hidden behind the modal, so role queries
    // cannot see it), and the ask is the same one.
    await user.keyboard("{F9}");
    expect(document.querySelector("aside")).not.toBeNull();
    expect(screen.getByRole("dialog")).toBe(dialog);

    // A second navigation while the ask stands is refused outright — the
    // ask that stands keeps its resolver, so answering it completes the
    // navigation that asked, not whatever tried to cut in line. (A user
    // event cannot reach this path: a pointer press outside the dialog is
    // the dismissal, and the click that follows asks anew.)
    await act(async () => {
      await router.navigate({ to: "/novels/$id", params: { id: NOVEL_ID } });
    });
    expect(screen.getByRole("dialog")).toBe(dialog);
    await user.click(screen.getByRole("button", { name: t("save.leaveGo") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(chapterRow(1).getAttribute("aria-current")).toBe("true"));
    expect(document.querySelector(".ProseMirror")?.textContent).toBe("Anfang.");
  });

  it("an accepted ask on a panel toggle keeps the notice and the guard armed", { timeout: 10_000 }, async () => {
    const { user } = await renderWithFailedSave();

    // The toggle's navigation completes — the rail collapses — but the
    // refused body is not dropped on the way: the panel moving is no
    // chapter switch, so the failure notice stays beside the text. The
    // toggle is the toolbar's one rail control now: the same button
    // brings the rail back.
    await user.click(screen.getByRole("button", { name: t("workspace.railToggle") }));
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("button", { name: t("save.leaveGo") }));
    await waitFor(() => expect(screen.queryByRole("complementary")).toBeNull());
    expect(screen.getByRole("button", { name: t("workspace.railToggle") })).toBeTruthy();
    expect(screen.getByText(t("save.failed"))).toBeTruthy();

    // And the gate is still armed: the next navigation asks again, because
    // the body it would leave behind is still only in the browser.
    await user.click(screen.getByRole("button", { name: t("workspace.railToggle") }));
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("button", { name: t("save.leaveGo") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("a search-only navigation meets the gate too, and a dismissed ask keeps the panel", { timeout: 10_000 }, async () => {
    const { user } = await renderWithFailedSave();

    // Collapsing the rail is a navigation inside the book — a search-only
    // one — and the widened gate asks for the refused body all the same.
    // Dismissed, the panel state stays exactly where it was.
    await user.click(screen.getByRole("button", { name: t("workspace.railToggle") }));
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("button", { name: t("save.leaveStay") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByRole("complementary")).toBeTruthy();
    expect(screen.getByRole("button", { name: t("workspace.railToggle") })).toBeTruthy();
    expect(document.querySelector(".ProseMirror")?.textContent).toContain("Bleibt hier.");
  });
});

describe("the created chapter's selection", () => {
  it("moves to the new chapter once the list holds it, not waiting for the novels refetch", { timeout: 10_000 }, async () => {
    // The novel row's refetch hangs: the create invalidates the ["novels"]
    // prefix, and that ask never answers. The selection waits only for the
    // chapters list it names.
    let novelReads = 0;
    let chapterReads = 0;
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") return { data: { locale: null }, response: ok() };
      if (path === "/api/writing/novels/{novel_id}") {
        novelReads += 1;
        if (novelReads === 1) return { data: NOVEL, response: ok() };
        return new Promise(() => {});
      }
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        chapterReads += 1;
        return { data: chapterReads === 1 ? CHAPTERS : TWO_CHAPTERS, response: ok() };
      }
      throw new Error(`unexpected GET ${path}`);
    });
    api.POST.mockResolvedValue({ data: TWO_CHAPTERS[1], response: ok() });
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();
    await user.click(screen.getByRole("button", { name: t("chapters.new") }));

    // The list landed — the ask the selection waits for — and the editor
    // flipped to the created chapter while the novel row's refetch was
    // still outstanding: the flip never queues behind the rest of the
    // book.
    await waitFor(() =>
      expect(chapterRow(2).getAttribute("aria-current")).toBe("true"),
    );
    expect(document.querySelector(".ProseMirror")?.textContent).toBe("");
    expect(novelReads).toBe(2);
  });
});

describe("the palette's novel jump", () => {
  it("a same-mount jump to another book selects that book's last-touched chapter", { timeout: 10_000 }, async () => {
    // Both books answer, each with its own rows: the palette's jump is an
    // ordinary navigation, and the route stays mounted while only the param
    // changes — exactly the case a latch keyed to nothing got wrong, by
    // keeping the first book's row as the second book's answer.
    api.GET.mockImplementation(
      async (path: string, init?: { params?: { path?: { novel_id?: string } } }) => {
        if (path === "/api/settings") return { data: { locale: null }, response: ok() };
        const novelId = init?.params?.path?.novel_id;
        if (path === "/api/writing/novels/{novel_id}") {
          return { data: novelId === NOVEL_ID ? NOVEL : OTHER_NOVEL, response: ok() };
        }
        if (path === "/api/writing/novels/{novel_id}/chapters") {
          return { data: novelId === NOVEL_ID ? CHAPTERS : OTHER_CHAPTERS, response: ok() };
        }
        throw new Error(`unexpected GET ${path}`);
      },
    );
    const router = renderAt(`/novels/${NOVEL_ID}`);
    await editorElement();

    await act(async () => {
      await router.navigate({ to: "/novels/$id", params: { id: OTHER_NOVEL_ID } });
    });

    // The other book's own last-touched chapter is selected — the new
    // book's choice, not the first book's row carried across, and not
    // nothing.
    await waitFor(() =>
      expect(chapterRow(1).getAttribute("aria-current")).toBe("true"),
    );
    expect(document.querySelector(".ProseMirror")?.textContent).toBe("Anderer Anfang.");
    expect(screen.getByRole("heading", { name: OTHER_NOVEL.title })).toBeTruthy();
  });
});

describe("the rail's reorder", () => {
  /** A rail row by its title: named rows are identity-stable across a
   *  reorder, where position-derived labels move with the swap. */
  function titledRow(title: string): HTMLElement {
    return screen.getByRole("button", { name: new RegExp(`^${title}\\b`) });
  }

  /** Two chapters in the rail, a workbench around them, and the keyboard
   *  driver — the state every case in this block starts from. The named
   *  pair for the cases that watch the DOM order, the unnamed one for
   *  the cases that watch the announcement's fallback label. */
  async function renderTwoChapters(named = true) {
    (named ? mockTwoNamedChapters : mockTwoChapters)();
    api.PUT.mockResolvedValue({ response: ok() });
    renderAt(`/novels/${NOVEL_ID}`);
    await editorElement();
    return userEvent.setup({ pointerEventsCheck: 0 });
  }

  it("alt_arrow_down_moves_the_focused_chapter", { timeout: 10_000 }, async () => {
    const user = await renderTwoChapters();

    // Alt+ArrowDown on the focused row is a move, not a walk: the row the
    // focus holds trades places with its neighbour.
    titledRow("Erstes").focus();
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");

    // The PUT carries the whole rail in its new order — every id, the
    // arrangement as one permutation.
    await waitFor(() =>
      expect(api.PUT).toHaveBeenCalledWith(
        "/api/writing/novels/{novel_id}/chapter-order",
        {
          params: { path: { novel_id: NOVEL_ID } },
          body: { chapter_ids: [SECOND_CHAPTER_ID, CHAPTER_ID] },
        },
      ),
    );
    // The optimistic order is the rail's at once: the second chapter's
    // row is the list's first, before any answer arrives.
    expect(railOrder()).toEqual([1, 0]);
    // The cache holds the same arrangement with positions rewritten to
    // match — the numbering the rows now render is the cache's own.
    const cached = queryClient.getQueryData<Array<Chapter>>(["chapters", NOVEL_ID]);
    expect(cached?.map((row) => row.id)).toEqual([SECOND_CHAPTER_ID, CHAPTER_ID]);
    expect(cached?.map((row) => row.position)).toEqual([0, 1]);
  });

  it("a_refused_order_reverts_and_names_the_refusal", { timeout: 10_000 }, async () => {
    mockTwoNamedChapters();
    // A second tab rearranged the book first: the PUT answers 409, the
    // one refusal whose truth the rail's own cache lacks.
    api.PUT.mockResolvedValue({ response: new Response(null, { status: 409 }) });
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    titledRow("Erstes").focus();
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");

    // The refusal is named in the rail, beside the button that asks…
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("chapters.orderFailed"));
    // …the optimistic arrangement is gone — the rail and the cache are
    // the ones they were…
    expect(railOrder()).toEqual([0, 1]);
    const cached = queryClient.getQueryData<Array<Chapter>>(["chapters", NOVEL_ID]);
    expect(cached?.map((row) => row.id)).toEqual([CHAPTER_ID, SECOND_CHAPTER_ID]);
    // …and the 409 asked the chapters key to refetch: the server's whole
    // is the arrangement the cache cannot know. The shelf was asked for
    // nothing — the reorder never happened, and a failed write never
    // asks for anything it did not do.
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["chapters", NOVEL_ID] }),
    );
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ["novels"] });
    invalidate.mockRestore();
  });

  it("a_successful_move_invalidates_the_shelf", { timeout: 10_000 }, async () => {
    const user = await renderTwoChapters(false);
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    chapterRow(1).focus();
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");

    // The arrangement advanced the novel's row (D8), so the shelf is
    // asked for again — and the chapters key is not: the optimistic
    // order is what the 204 acknowledged, and a refetch mid-unsaved-body
    // is exactly the state the save-side rule guards against.
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["novels"] }),
    );
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ["chapters", NOVEL_ID] });
    invalidate.mockRestore();
  });

  it("the_move_is_announced_with_its_new_position", { timeout: 10_000 }, async () => {
    const user = await renderTwoChapters(false);
    clearAnnouncements();

    chapterRow(1).focus();
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");

    // A plain list tells AT nothing about a reordering: every move is
    // announced — the row's composed label (the position-derived one for
    // an untitled chapter), the position it holds now, out of the book's
    // total. The label leads the sentence exactly once, in any locale:
    // a key that wrapped it in a kind word it already carries
    // ("Kapitel Kapitel 1, …") would neither start with the label nor
    // keep it singular — two pins, both locale-free.
    const said = document.querySelector("[data-live-announcer]")?.textContent ?? "";
    const label = t("chapters.defaultTitle", { n: 1 });
    const spoken = said.trim();
    expect(spoken).toContain(t("chapters.moved", { title: label, n: 2, m: 2 }));
    expect(spoken.startsWith(label)).toBe(true);
    expect(spoken.split(label).length - 1).toBe(1);
  });

  it("a_failed_move_does_not_clobber_a_later_moves_order", { timeout: 10_000 }, async () => {
    // Key repeat is two moves in one breath: the first ask fails, the
    // second lands. The first move's failure must restore nothing — the
    // cache no longer holds its arrangement, and clobbering the later
    // move's optimistic order with the earlier snapshot would show a
    // rail the server never held.
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        return { data: THREE_NAMED_CHAPTERS, response: ok() };
      }
      return loadedAnswer(path);
    });
    // The answers land on the test's clock, not the mock's: key repeat
    // fires both keystrokes before any network answer exists, so both
    // arrangements are outstanding at once when the earlier one fails.
    const answers: Array<(value: { response: Response }) => void> = [];
    api.PUT.mockImplementation(
      () => new Promise((resolve) => answers.push(resolve as never)),
    );
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    // Move A: Erstes down one — [Zweites, Erstes, Drittes]; its PUT fails.
    titledRow("Erstes").focus();
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");
    // Move B: Drittes up one, computed from A's arrangement —
    // [Zweites, Drittes, Erstes]; its PUT is the one that lands.
    titledRow("Drittes").focus();
    await user.keyboard("{Alt>}{ArrowUp}{/Alt}");

    // The queue is one arrangement wide: A's ask flew, B's waits its
    // turn — two PUTs can never be on the wire together committing
    // inverted. Both keystrokes have happened by now.
    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(1));
    expect(api.PUT).toHaveBeenLastCalledWith(
      "/api/writing/novels/{novel_id}/chapter-order",
      {
        params: { path: { novel_id: NOVEL_ID } },
        body: { chapter_ids: [SECOND_CHAPTER_ID, CHAPTER_ID, THIRD_CHAPTER_ID] },
      },
    );

    // A's answer lands as a failure — and the queue releases B's ask,
    // which carries the arrangement B computed from A's optimistic one.
    await act(async () => {
      answers[0]?.({ response: new Response(null, { status: 500 }) });
      await Promise.resolve();
    });
    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(2));
    expect(api.PUT).toHaveBeenLastCalledWith(
      "/api/writing/novels/{novel_id}/chapter-order",
      {
        params: { path: { novel_id: NOVEL_ID } },
        body: { chapter_ids: [SECOND_CHAPTER_ID, THIRD_CHAPTER_ID, CHAPTER_ID] },
      },
    );

    // B's answer lands as the success it is.
    await act(async () => {
      answers[1]?.({ response: ok() });
      await Promise.resolve();
    });

    // The failure is still named — one of the moves did not land…
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("chapters.orderFailed"));
    // …but the rail holds the arrangement that did: Zweites leads and
    // Erstes is last (B's order), not the original A would have restored.
    expect(railOrder()).toEqual([2, 0]);
    const cached = queryClient.getQueryData<Array<Chapter>>(["chapters", NOVEL_ID]);
    expect(cached?.map((row) => row.id)).toEqual([
      SECOND_CHAPTER_ID,
      THIRD_CHAPTER_ID,
      CHAPTER_ID,
    ]);
  });

  it("a_lone_failed_move_reverts_the_rail", { timeout: 10_000 }, async () => {
    // One move, one refusal, nothing queued behind it. A transport
    // failure (500) asks for no refetch — nothing rescues the cache — so
    // the restore itself is the only thing that can put the rail back:
    // the optimistic arrangement must come back off, or it stays on the
    // screen forever claiming an order the server never took.
    mockTwoNamedChapters();
    api.PUT.mockResolvedValue({ response: new Response(null, { status: 500 }) });
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    titledRow("Erstes").focus();
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");

    // The refusal is named, and the rail and the cache are the ones they
    // were — the revert, not a refetch, put them there.
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("chapters.orderFailed"));
    expect(railOrder()).toEqual([0, 1]);
    const cached = queryClient.getQueryData<Array<Chapter>>(["chapters", NOVEL_ID]);
    expect(cached?.map((row) => row.id)).toEqual([CHAPTER_ID, SECOND_CHAPTER_ID]);
    expect(cached?.map((row) => row.position)).toEqual([0, 1]);
  });

  it("a_drag_and_drop_moves_the_chapter", { timeout: 10_000 }, async () => {
    // Beyond the brief's four: the E2E is the keyboard's (drag under
    // Playwright is the spec's named flake), so the drag path's only
    // proof is here, at the DOM — drivable because the dragged id rides
    // component state, never dataTransfer.
    await renderTwoChapters();

    const slots = screen
      .getByRole("complementary")
      .querySelectorAll<HTMLLIElement>("ul > li");
    expect(slots.length).toBe(2);
    fireEvent.dragStart(titledRow("Erstes"));
    fireEvent.dragOver(slots[1]!);
    fireEvent.drop(slots[1]!);
    fireEvent.dragEnd(titledRow("Erstes"));

    await waitFor(() =>
      expect(api.PUT).toHaveBeenCalledWith(
        "/api/writing/novels/{novel_id}/chapter-order",
        {
          params: { path: { novel_id: NOVEL_ID } },
          body: { chapter_ids: [SECOND_CHAPTER_ID, CHAPTER_ID] },
        },
      ),
    );
    expect(railOrder()).toEqual([1, 0]);
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
    const pulsing = document.querySelectorAll('[class*="animate-pulse"]');
    expect(pulsing.length).toBeGreaterThanOrEqual(4);
    // The pulse rides the motion-safe variant: prefers-reduced-motion: reduce
    // stops it (F24) — the class string is the pinned contract.
    for (const skeleton of pulsing) {
      expect(skeleton.className).toContain("motion-safe:animate-pulse");
    }
    // The wait is not an outage: nothing claims the shelf failed.
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
