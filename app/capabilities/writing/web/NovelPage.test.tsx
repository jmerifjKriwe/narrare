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
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { clearAnnouncements } from "@shell/lib/announce";
import { t } from "@shell/lib/i18n";
import { activeLocale, applyLocale } from "@shell/lib/locale";
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

describe("a book deleted elsewhere", () => {
  it("a_novel_deleted_elsewhere_degrades_to_the_shelf", { timeout: 10_000 }, async () => {
    // The real 404 the API answers for a deleted book — not a component
    // error: the novel's row is gone, whatever the workspace still holds.
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") return { data: { locale: null }, response: ok() };
      if (path === "/api/setup/status") return { data: { complete: true }, response: ok() };
      if (path === "/api/writing/novels") return { data: [NOVEL], response: ok() };
      if (path === "/api/writing/novels/{novel_id}") {
        return { data: undefined, response: new Response(null, { status: 404 }) };
      }
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        return { data: CHAPTERS, response: ok() };
      }
      throw new Error(`unexpected GET ${path}`);
    });
    renderAt(`/novels/${NOVEL_ID}`);

    // The shelf takes the address over — no outage page for a book that
    // was never missing, only deleted — and the quiet notice names what
    // happened: status speech, not an alert, because nothing here asks the
    // user to fix anything.
    expect(await screen.findByRole("heading", { name: t("novels.heading") })).toBeTruthy();
    const notice = await screen.findByText(t("novels.deleteElsewhere"));
    expect(notice.getAttribute("role")).toBe("status");
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("the rail's reorder", () => {
  /** A rail row by its title: named rows are identity-stable across a
   *  reorder, where position-derived labels move with the swap. The row's
   *  name is the title followed by its word count, so the predicate takes
   *  the whole leading title — "Kapitel 1" never matches "Kapitel 10". */
  function titledRow(title: string): HTMLElement {
    return screen.getByRole("button", {
      name: (name: string) => name === title || name.startsWith(`${title} `),
    });
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

  it("a_refused_move_from_the_runhead_is_named_with_the_rail_hidden", { timeout: 10_000 }, async () => {
    mockTwoNamedChapters();
    // A second tab rearranged the book first: the PUT answers 409.
    api.PUT.mockResolvedValue({ response: new Response(null, { status: 409 }) });
    // The rail collapsed: the runhead's move items are still offered —
    // and the refusal must be named on a surface that is on screen.
    // (`?rail=false`, the toggle's own encoding: this router carries no
    // validateSearch, and the raw parser hands booleans, not the 0 the
    // page's own route would normalize.)
    renderAt(`/novels/${NOVEL_ID}?rail=false`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();
    expect(screen.queryByRole("complementary")).toBeNull();

    // The last-touched chapter is the open one; its menu offers the move.
    const openTitle = "Zweites";
    await user.click(screen.getByRole("button", { name: t("chapters.actionsFor", { title: openTitle }) }));
    await user.click(screen.getByRole("menuitem", { name: t("chapters.moveUp") }));

    // The refusal is named in the editor column, the surface that stayed.
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("chapters.orderFailed"));
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

describe("the rail's filter", () => {
  /** A book of many chapters: positions 0..n-1, unique ids, timestamps that
   *  run with the position so the last row is the book's last-touched —
   *  unless `touched` names another row as the one the fallback opens. */
  function manyChapters(
    count: number,
    titled: Record<number, string> = {},
    touched = count - 1,
  ): Array<Chapter> {
    const rows = Array.from({ length: count }, (_, position) => ({
      id: `00000000-0000-4000-8000-${String(position).padStart(12, "0")}`,
      novel_id: NOVEL_ID,
      title: titled[position] ?? "",
      body: "",
      position,
      created_at: "2026-10-30T09:00:00Z",
      updated_at: `2026-10-30T10:${String(position % 60).padStart(2, "0")}:00Z`,
    }));
    rows[touched] = { ...rows[touched], updated_at: "2026-10-30T23:00:00Z" };
    return rows;
  }

  /** The loaded answers with a long book in the rail's list. */
  function mockManyChapters(
    count: number,
    titled: Record<number, string> = {},
    touched = count - 1,
  ): void {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        return { data: manyChapters(count, titled, touched), response: ok() };
      }
      return loadedAnswer(path);
    });
  }

  /** The runhead's menu trigger: named for the chapter it acts on. */
  function menuTrigger(title: string): HTMLElement {
    return screen.getByRole("button", { name: t("chapters.actionsFor", { title }) });
  }

  it("the_filter_appears_only_above_twenty_chapters", { timeout: 10_000 }, async () => {
    // Twenty chapters: the rail stays as it was — the field is the long
    // rail's own, not the book's.
    mockManyChapters(20);
    renderAt(`/novels/${NOVEL_ID}`);
    await editorElement();
    expect(screen.queryByRole("searchbox")).toBeNull();

    // Twenty-one: the band above the rail gains the field.
    cleanup();
    queryClient.clear();
    mockManyChapters(21);
    renderAt(`/novels/${NOVEL_ID}`);
    await editorElement();
    expect(screen.getByRole("searchbox")).toBeTruthy();
  });

  it("the_filter_matches_an_untitled_chapters_rendered_label", { timeout: 10_000 }, async () => {
    mockManyChapters(21);
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    // An untitled chapter is named by what its row says — the localized
    // number — so that is what the filter answers to: the rendered label
    // in the active locale, not the row's stored (empty) title.
    await user.type(screen.getByRole("searchbox"), t("chapters.defaultTitle", { n: 7 }));

    const rail = screen.getByRole("complementary");
    expect(rail.querySelectorAll("li > button").length).toBe(1);
    expect(chapterRow(7)).toBeTruthy();
  });

  it("the_filter_matches_diacritics_insensitively", { timeout: 10_000 }, async () => {
    mockManyChapters(21, { 0: "Fürstenwald", 1: "Furth" });
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    // A bare "fur" finds the umlauted title, and the umlauted needle finds
    // the bare one: neither side's diacritics decide a match.
    await user.type(screen.getByRole("searchbox"), "fur");
    const rail = screen.getByRole("complementary");
    expect(rail.querySelectorAll("li > button").length).toBe(2);
    expect(screen.getByRole("button", { name: /^Fürstenwald\b/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Furth\b/ })).toBeTruthy();

    await user.clear(screen.getByRole("searchbox"));
    await user.type(screen.getByRole("searchbox"), "für");
    expect(rail.querySelectorAll("li > button").length).toBe(2);
    expect(screen.getByRole("button", { name: /^Fürstenwald\b/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Furth\b/ })).toBeTruthy();
  });

  it("creating_a_chapter_clears_the_filter", { timeout: 10_000 }, async () => {
    // A stateful list: the create's POST grows the book the next GET
    // answers with — the same refetch the invalidation triggers.
    const rows = manyChapters(21);
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        return { data: rows.map((row) => ({ ...row })), response: ok() };
      }
      return loadedAnswer(path);
    });
    api.POST.mockImplementation(async () => {
      const created = {
        id: `00000000-0000-4000-8000-${String(rows.length).padStart(12, "0")}`,
        novel_id: NOVEL_ID,
        title: "",
        body: "",
        position: rows.length,
        created_at: "2026-10-30T11:00:00Z",
        updated_at: "2026-10-30T11:00:00Z",
      };
      rows.push(created);
      return { data: { ...created }, response: ok() };
    });
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    // A filter that hides every row the book has.
    await user.type(screen.getByRole("searchbox"), "Niemals");
    expect(screen.getByRole("complementary").querySelectorAll("li > button").length).toBe(0);

    // The create clears it — the new chapter must land in the visible
    // list, and it does: the field is empty and the new row is current.
    await user.click(screen.getByRole("button", { name: t("chapters.new") }));
    const filter = screen.getByRole("searchbox") as HTMLInputElement;
    await waitFor(() => expect(filter.value).toBe(""));
    await waitFor(() =>
      expect(chapterRow(22).getAttribute("aria-current")).toBe("true"),
    );
    expect(screen.getByRole("complementary").querySelectorAll("li > button").length).toBe(22);
  });

  it("the_move_menu_items_are_disabled_while_the_filter_is_active", { timeout: 10_000 }, async () => {
    // The tenth chapter is the book's last-touched (the fallback opens it):
    // a middle row, so the filter — not the book's ends — is the only
    // thing that can disable the move items.
    mockManyChapters(21, {}, 9);
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();
    const openTitle = t("chapters.defaultTitle", { n: 10 });
    expect(chapterRow(10).getAttribute("aria-current")).toBe("true");

    // Without a filter the items are offered enabled (Task 10's contract).
    await user.click(menuTrigger(openTitle));
    expect(
      screen.getByRole("menuitem", { name: t("chapters.moveUp") }).getAttribute("aria-disabled"),
    ).not.toBe("true");
    await user.keyboard("{Escape}");

    // With a filter they disable and say why: the label itself carries the
    // reason, not a tooltip beside it. The needle keeps the open chapter
    // visible (its rendered label contains the first chapter's).
    await user.type(screen.getByRole("searchbox"), t("chapters.defaultTitle", { n: 1 }));
    await user.click(menuTrigger(openTitle));
    expect(
      screen.getByRole("menuitem", { name: t("chapters.moveUpFiltered") }).getAttribute(
        "aria-disabled",
      ),
    ).toBe("true");
    expect(
      screen.getByRole("menuitem", { name: t("chapters.moveDownFiltered") }).getAttribute(
        "aria-disabled",
      ),
    ).toBe("true");
    expect(screen.queryByRole("menuitem", { name: t("chapters.moveUp") })).toBeNull();
    await user.keyboard("{Escape}");

    // The keyboard's move and the drag are the menu's equals: Alt+↓ on a
    // visible row moves nothing while the filter stands, and no row
    // offers a grab.
    expect((chapterRow(10) as HTMLElement).draggable).toBe(false);
    chapterRow(10).focus();
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");
    expect(api.PUT).not.toHaveBeenCalled();

    // A filter that hides the OPEN chapter leaves the keyboard a way in —
    // and so does a walk the filter cut short. The walk is over when the
    // question changes: its row may be gone, and the first visible row
    // takes the stop either way.
    const search = screen.getByRole("searchbox");
    chapterRow(11).focus();
    await user.keyboard("{ArrowDown}"); // the walk: chapter 11 → 12
    expect(chapterRow(12).getAttribute("tabindex")).toBe("0");
    await user.clear(search);
    await user.type(search, t("chapters.defaultTitle", { n: 21 }));
    const hiddenTitle = t("chapters.defaultTitle", { n: 10 });
    expect(
      screen.queryByRole("button", {
        name: (name: string) => name === hiddenTitle || name.startsWith(`${hiddenTitle} `),
      }),
    ).toBeNull();
    expect(chapterRow(21).getAttribute("tabindex")).toBe("0");
  });

  it("a_standing_filter_rematches_after_a_locale_switch", { timeout: 10_000 }, async () => {
    // One titled row is the control: its label never changes with the
    // language. Everything else on screen is the localized number, and a
    // question asked in one language must be re-asked — not replayed —
    // when the rows change their words.
    const was = activeLocale();
    mockManyChapters(21, { 0: "Waldlauf" });
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();
    const rail = screen.getByRole("complementary");

    try {
      applyLocale("en");
      await user.clear(screen.getByRole("searchbox"));
      await user.type(screen.getByRole("searchbox"), "Chapter");
      expect(rail.querySelectorAll("li > button").length).toBe(20);
      expect(
        screen.queryByRole("button", { name: /^Waldlauf\b/ }),
      ).toBeNull();

      // German rows say "Kapitel n": the standing English question no
      // longer describes any of them, and the filter re-matches instead of
      // replaying the English answer.
      applyLocale("de");
      await waitFor(() =>
        expect(rail.querySelectorAll("li > button").length).toBe(0),
      );
    } finally {
      applyLocale(was);
    }
  });
});

describe("the runhead's action menu", () => {
  /** Three named chapters as a book the writes mutate: a stateful list, so
   *  a delete or rename is answered by the very next read the way the
   *  server would answer it. */
  function mockStateful(
    initial: Array<typeof CHAPTERS[number]>,
    novel: Record<string, unknown> = NOVEL,
  ): { rows: Array<typeof CHAPTERS[number]> } {
    const rows = initial.map((row) => ({ ...row }));
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") return { data: { locale: null }, response: ok() };
      if (path === "/api/writing/novels/{novel_id}") return { data: novel, response: ok() };
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        return { data: rows.map((row) => ({ ...row })), response: ok() };
      }
      throw new Error(`unexpected GET ${path}`);
    });
    api.PUT.mockImplementation(
      async (
        _path: string,
        init: { params: { path: { chapter_id: string } }; body: Record<string, string> },
      ) => {
        const row = rows.find((each) => each.id === init.params.path.chapter_id);
        if (!row) return { response: refused() };
        Object.assign(row, init.body);
        row.updated_at = new Date().toISOString();
        return { data: { ...row }, response: ok() };
      },
    );
    api.DELETE.mockImplementation(
      async (_path: string, init: { params: { path: { chapter_id: string } } }) => {
        const index = rows.findIndex((each) => each.id === init.params.path.chapter_id);
        if (index < 0) return { response: new Response(null, { status: 404 }) };
        rows.splice(index, 1);
        rows.forEach((row, position) => {
          row.position = position;
        });
        return { response: new Response(null, { status: 204 }) };
      },
    );
    return { rows };
  }

  /** The runhead's menu trigger: named for the chapter it acts on. */
  function menuTrigger(title: string): HTMLElement {
    return screen.getByRole("button", { name: t("chapters.actionsFor", { title }) });
  }

  /** A rail row by its title — the reorder block's own finder, mirrored
   *  for the named chapters these cases delete and rename. */
  function titledRow(title: string): HTMLElement {
    return screen.getByRole("button", { name: new RegExp(`^${title}\\b`) });
  }

  /** The runhead's title input, by its accessible name. */
  function runheadTitle(): HTMLInputElement {
    return screen.getByLabelText(t("chapters.titleLabel")) as HTMLInputElement;
  }

  /** Delete the open chapter the way a user does: the menu, the item, the
   *  dialog's confirm. */
  async function deleteThroughMenu(
    user: ReturnType<typeof userEvent.setup>,
    title: string,
  ): Promise<void> {
    await user.click(menuTrigger(title));
    await user.click(screen.getByRole("menuitem", { name: t("chapters.delete") }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: t("chapters.delete") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  }

  it("the_runhead_menu_offers_rename_delete_and_move", { timeout: 10_000 }, async () => {
    mockStateful(THREE_NAMED_CHAPTERS);
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    // The rail is untouched by the menu's presence: three plain rows, no
    // menu markup nested anywhere in them (UI-B's rows stay as they were).
    expect(screen.getByRole("complementary").querySelectorAll("li > button").length).toBe(3);

    // The book's last-touched chapter (Zweites, the middle one) is open;
    // its menu offers the four actions, and the move items carry the
    // shortcut the rail already answers to (D6: the hint is discoverable
    // exactly where the action lives).
    await user.click(menuTrigger("Zweites"));
    expect(screen.getByRole("menuitem", { name: t("chapters.rename") })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: t("chapters.delete") })).toBeTruthy();
    // The move items carry their shortcut as a visible hint and in
    // `aria-keyshortcuts` — the accessible name is the label alone.
    const up = screen.getByRole("menuitem", { name: t("chapters.moveUp") });
    const down = screen.getByRole("menuitem", { name: t("chapters.moveDown") });
    expect(up.textContent).toContain("Alt+↑");
    expect(down.textContent).toContain("Alt+↓");
    // A middle chapter can move both ways: neither item is disabled.
    expect(up.getAttribute("aria-disabled")).not.toBe("true");
    expect(down.getAttribute("aria-disabled")).not.toBe("true");

    // The menu's move is the rail's own move: one PUT of the whole rail,
    // the arrangement the keyboard's Alt+↓ would have written — Zweites
    // trades places with Drittes.
    await user.click(down);
    await waitFor(() =>
      expect(api.PUT).toHaveBeenCalledWith(
        "/api/writing/novels/{novel_id}/chapter-order",
        {
          params: { path: { novel_id: NOVEL_ID } },
          body: { chapter_ids: [CHAPTER_ID, THIRD_CHAPTER_ID, SECOND_CHAPTER_ID] },
        },
      ),
    );
  });

  it("deleting_the_open_chapter_opens_its_neighbour", { timeout: 10_000 }, async () => {
    const { rows } = mockStateful(THREE_NAMED_CHAPTERS);
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    // The next chapter takes the deleted one's place: delete Erstes, the
    // book's first, and Zweites opens.
    await user.click(titledRow("Erstes"));
    await deleteThroughMenu(user, "Erstes");
    expect(api.DELETE).toHaveBeenCalledWith("/api/writing/chapters/{chapter_id}", {
      params: { path: { chapter_id: CHAPTER_ID } },
    });
    await waitFor(() =>
      expect(titledRow("Zweites").getAttribute("aria-current")).toBe("true"),
    );
    expect(screen.getByLabelText(t("chapters.titleLabel"))).toBeTruthy();
    expect(runheadTitle().value).toBe("Zweites");
    expect(rows.map((row) => row.id)).toEqual([SECOND_CHAPTER_ID, THIRD_CHAPTER_ID]);

    // The last chapter has no next: the previous one takes its place.
    await user.click(titledRow("Drittes"));
    await deleteThroughMenu(user, "Drittes");
    await waitFor(() =>
      expect(titledRow("Zweites").getAttribute("aria-current")).toBe("true"),
    );

    // The book's last remaining chapter: no neighbour, the empty state —
    // and the row is gone from the list the server would answer with.
    await deleteThroughMenu(user, "Zweites");
    await waitFor(() => expect(screen.getByText(t("chapters.empty"))).toBeTruthy());
    expect(document.querySelector(".ProseMirror")).toBeNull();
    expect(rows).toEqual([]);
  });

  it("deleting_the_open_chapter_retires_the_pending_save", { timeout: 10_000 }, async () => {
    const { rows } = mockStateful(TWO_NAMED_CHAPTERS);
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    (await editorElement()).focus();
    // A body edit pending on the open chapter (Zweites, the book's
    // last-touched) — inside the debounce, nothing on the wire yet.
    await user.keyboard("Bleibt nicht.");
    expect(api.PUT).not.toHaveBeenCalled();

    await deleteThroughMenu(user, "Zweites");

    // The neighbour opened, the DELETE flew — and the pending body was
    // retired before it: no PUT at a chapter on its way out.
    await waitFor(() =>
      expect(titledRow("Erstes").getAttribute("aria-current")).toBe("true"),
    );
    expect(api.DELETE).toHaveBeenCalledWith("/api/writing/chapters/{chapter_id}", {
      params: { path: { chapter_id: SECOND_CHAPTER_ID } },
    });
    // Past the debounce: the timer's flush finds the slot the delete
    // emptied — and no failed status was ever named for a deletion the
    // user asked for.
    await new Promise((resolve) => setTimeout(resolve, 1100));
    expect(api.PUT).not.toHaveBeenCalled();
    expect(screen.queryByText(t("save.failed"))).toBeNull();
    expect(rows.map((row) => row.id)).toEqual([CHAPTER_ID]);
  });

  it("renaming_the_open_chapter_survives_the_next_debounce", { timeout: 10_000 }, async () => {
    mockStateful(TWO_NAMED_CHAPTERS);
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    (await editorElement()).focus();
    // A body edit pending on the open chapter (Zweites): the rename must
    // not wait for it, and the flush that follows must not undo it.
    await user.keyboard(" Ein Satz.");

    await user.click(menuTrigger("Zweites"));
    await user.click(screen.getByRole("menuitem", { name: t("chapters.rename") }));
    const dialog = await screen.findByRole("dialog");
    const input = within(dialog).getByLabelText(t("chapters.renameLabel"));
    await user.clear(input);
    await user.type(input, "Winternacht");
    await user.click(within(dialog).getByRole("button", { name: t("chapters.rename") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    // The dialog's write carried the title alone…
    await waitFor(() =>
      expect(api.PUT).toHaveBeenCalledWith("/api/writing/chapters/{chapter_id}", {
        params: { path: { chapter_id: SECOND_CHAPTER_ID } },
        body: { title: "Winternacht" },
      }),
    );
    // …the runhead wears the new name at once…
    expect(runheadTitle().value).toBe("Winternacht");

    // …and the next flush carries the body only — the title is not dirty,
    // so the rename survives the debounce it met (Task 9's contract).
    await waitFor(
      () =>
        expect(api.PUT).toHaveBeenLastCalledWith("/api/writing/chapters/{chapter_id}", {
          params: { path: { chapter_id: SECOND_CHAPTER_ID } },
          body: { body: " Ein Satz." },
        }),
      { timeout: 4000 },
    );
    const chapterPuts = api.PUT.mock.calls.filter(
      ([path]) => path === "/api/writing/chapters/{chapter_id}",
    );
    expect(chapterPuts).toHaveLength(2);
    expect(Object.keys(chapterPuts[1]![1].body)).toEqual(["body"]);
    // The new title stands: the rail answers to it, not to the name the
    // flush's draft was holding when the rename landed.
    await waitFor(() => expect(titledRow("Winternacht")).toBeTruthy());
    expect(runheadTitle().value).toBe("Winternacht");
  });

  it("the_delete_dialog_names_the_chapter_and_the_export_age", { timeout: 10_000 }, async () => {
    const exportedAt = new Date(Date.now() - 3 * 86_400_000).toISOString();
    mockStateful(THREE_NAMED_CHAPTERS, { ...NOVEL, last_exported_at: exportedAt });
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    // The dialog names what dies — the chapter, by its own name — and the
    // scoped export line: this chapter was last written before the export,
    // so it reads as unchanged since (the fresh line, days and all).
    await user.click(menuTrigger("Zweites"));
    await user.click(screen.getByRole("menuitem", { name: t("chapters.delete") }));
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText(t("chapters.deleteBody", { title: "Zweites" })),
    ).toBeTruthy();
    expect(within(dialog).getByText(t("chapters.exportFresh", { count: 3 }))).toBeTruthy();

    // A dismissed ask deletes nothing.
    await user.click(within(dialog).getByRole("button", { name: t("chapters.cancel") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.DELETE).not.toHaveBeenCalled();
  });

  it("todays_export_reads_as_today_not_as_an_age", { timeout: 10_000 }, async () => {
    // The most common export is the one that just happened: the line must
    // read "Exported today — unchanged since.", not splice the plural's
    // zero branch into a sentence that still carries its "ago" — the
    // preposition lives inside the ICU branches, so no count can break
    // the sentence around it.
    const exportedAt = new Date().toISOString();
    mockStateful(THREE_NAMED_CHAPTERS, { ...NOVEL, last_exported_at: exportedAt });
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    await user.click(menuTrigger("Zweites"));
    await user.click(screen.getByRole("menuitem", { name: t("chapters.delete") }));
    const dialog = await screen.findByRole("dialog");
    const line = within(dialog).getByText(t("chapters.exportFresh", { count: 0 }));
    expect(line.textContent).toBe(t("chapters.exportFresh", { count: 0 }));
    // The known breakage, named: neither locale's zero branch may meet a
    // leftover age word.
    expect(t("chapters.exportFresh", { count: 0 })).not.toMatch(/today ago|heute ago/i);
  });

  it("the_export_line_reads_the_chapters_own_stamp_not_the_books", { timeout: 10_000 }, async () => {
    // Two chapters, one export: Erstes was last written before it, Zweites
    // after it — and the book's own row was touched before it too, so a
    // comparison against the novel's updated_at would call both fresh.
    // The line is each chapter's own story (§5's scoping): stale for the
    // one that changed, fresh for the one that did not.
    const exportedAt = new Date(Date.now() - 3 * 86_400_000).toISOString();
    const { rows } = mockStateful(THREE_NAMED_CHAPTERS, {
      ...NOVEL,
      last_exported_at: exportedAt,
    });
    rows[1].updated_at = new Date().toISOString();

    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    // Zweites (the book's last-touched, open by the fallback): changed
    // since the export.
    await user.click(menuTrigger("Zweites"));
    await user.click(screen.getByRole("menuitem", { name: t("chapters.delete") }));
    let dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(t("chapters.exportStale"))).toBeTruthy();
    await user.click(within(dialog).getByRole("button", { name: t("chapters.cancel") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    // Erstes: unchanged since — the same dialog, the same book, the same
    // export, a different chapter stamp and a different verdict.
    await user.click(titledRow("Erstes"));
    await user.click(menuTrigger("Erstes"));
    await user.click(screen.getByRole("menuitem", { name: t("chapters.delete") }));
    dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(t("chapters.exportFresh", { count: 3 }))).toBeTruthy();
    await user.click(within(dialog).getByRole("button", { name: t("chapters.cancel") }));
  });

  it("a_refused_delete_hands_the_retired_body_back", { timeout: 10_000 }, async () => {
    const { rows } = mockStateful(TWO_NAMED_CHAPTERS);
    // The delete is refused; every other write answers.
    api.DELETE.mockResolvedValue({ response: new Response(null, { status: 500 }) });
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    (await editorElement()).focus();
    await user.keyboard("Bleibt doch.");
    expect(api.PUT).not.toHaveBeenCalled();

    await user.click(menuTrigger("Zweites"));
    await user.click(screen.getByRole("menuitem", { name: t("chapters.delete") }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: t("chapters.delete") }));

    // The refusal is named where the retry is one press away, and the
    // dialog stays: nothing was deleted.
    await waitFor(() =>
      expect(within(dialog).getByText(t("chapters.errorDelete"))).toBeTruthy(),
    );
    await user.click(within(dialog).getByRole("button", { name: t("chapters.cancel") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    // The body the delete retired was handed back whole: only a restored
    // slot can put its words on the wire, and the guards read that state —
    // the debounce flush carries BOTH fields (the title's dirt is part of
    // what the guards protect; a body-only restore would leave the
    // document half-saved), the editor keeps it, and the chapter survives
    // the refused delete.
    await waitFor(
      () =>
        expect(api.PUT).toHaveBeenCalledWith(
          "/api/writing/chapters/{chapter_id}",
          {
            params: { path: { chapter_id: SECOND_CHAPTER_ID } },
            body: {
              title: "Zweites",
              body: "Bleibt doch.",
            },
          },
        ),
      { timeout: 4000 },
    );
    expect(document.querySelector(".ProseMirror")?.textContent).toContain("Bleibt doch.");
    expect(rows.length).toBe(2);
  });

  it("a_refused_delete_leaves_a_clean_chapter_clean", { timeout: 10_000 }, async () => {
    const { rows } = mockStateful(TWO_NAMED_CHAPTERS);
    api.DELETE.mockResolvedValue({ response: new Response(null, { status: 500 }) });
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    // A clean chapter — nothing typed, nothing pending, nothing failed.
    // The delete is refused and the ask dismissed: no phantom work may be
    // invented on the way back. The restore belongs to the words that
    // were pending, and there were none.
    await user.click(menuTrigger("Zweites"));
    await user.click(screen.getByRole("menuitem", { name: t("chapters.delete") }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: t("chapters.delete") }));
    await waitFor(() =>
      expect(within(dialog).getByText(t("chapters.errorDelete"))).toBeTruthy(),
    );
    await user.click(within(dialog).getByRole("button", { name: t("chapters.cancel") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    // Past the debounce: no PUT flew — the document is identical to the
    // server's, and an identical document is not unsaved work — and no
    // status was ever named, not a save and not a failure.
    await new Promise((resolve) => setTimeout(resolve, 1100));
    expect(api.PUT).not.toHaveBeenCalled();
    expect(screen.queryByText(t("save.saved"))).toBeNull();
    expect(screen.queryByText(t("save.failed"))).toBeNull();
    expect(rows.length).toBe(2);
  });

  it("the_trigger_names_the_chapter_the_draft_holds", { timeout: 10_000 }, async () => {
    mockStateful(TWO_NAMED_CHAPTERS);
    // The save never lands: the row keeps the old name, so the trigger's
    // name can only come from the page's held draft.
    api.PUT.mockImplementation(() => new Promise(() => {}));
    renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();

    // The runhead's title keystroke is in the draft and nowhere else yet:
    // the menu's trigger wears it at once, before any save could carry it
    // to the row the cache holds.
    await user.type(screen.getByLabelText(t("chapters.titleLabel")), "Winter");
    expect(
      screen.getByRole("button", { name: t("chapters.actionsFor", { title: "ZweitesWinter" }) }),
    ).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: t("chapters.actionsFor", { title: "Zweites" }) }),
    ).toBeNull();
  });

  it("deleting_the_latched_chapter_rederives_the_fallback", { timeout: 10_000 }, async () => {
    const { rows } = mockStateful(TWO_NAMED_CHAPTERS);
    // The bare address: the fallback opens the book's last-touched chapter
    // (Zweites), and the URL writes no param.
    const router = renderAt(`/novels/${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await editorElement();
    expect(titledRow("Zweites").getAttribute("aria-current")).toBe("true");

    await deleteThroughMenu(user, "Zweites");
    await waitFor(() =>
      expect(titledRow("Erstes").getAttribute("aria-current")).toBe("true"),
    );
    expect(rows.map((row) => row.id)).toEqual([CHAPTER_ID]);

    // Back at the bare address (where history's back lands): the latch no
    // longer names a dead row — the surviving chapter opens, and an
    // editor renders instead of a workbench with nothing in it.
    await act(async () => {
      await router.navigate({ to: "/novels/$id", params: { id: NOVEL_ID } });
    });
    await waitFor(() =>
      expect(titledRow("Erstes").getAttribute("aria-current")).toBe("true"),
    );
    expect(document.querySelector(".ProseMirror")).not.toBeNull();
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
