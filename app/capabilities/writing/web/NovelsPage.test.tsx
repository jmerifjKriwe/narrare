// @vitest-environment jsdom
/**
 * Two shelves in one file. The composition tests (Task 10) pin the drafted
 * page — the Literary Modernism shelf 1:1 against `screens/library/shelf`:
 * the hero derives from the last-touched novel, the metrics from the list,
 * every interim field renders spec §6.6's neutral exactly (streak "—",
 * the target bar hidden, every pill "Entwurf", the goal 0 and the
 * sparkline flat), search filters titles, the toggle switches views, a
 * long title keeps its full string in the accessible name, and every
 * drafted section stands — hero, metrics, filter row, grid, banner, empty
 * state.
 *
 * The card-action tests (Task 13) drive the dialogs behind the card's
 * action menu — Details, Export and Delete — and the two dialogs behind
 * them. The details dialog is the book's five metadata fields in the
 * new-book form's own refusal style, saving only what the user changed
 * (the PATCH's `model_fields_set` contract mirrored client-side); the
 * language is validated text, refused on its own field by the pattern and
 * by the server's 422 naming it. The delete dialog names what dies —
 * chapters from the card's row, entities from the knowledge list it opens
 * with — says documents survive, and carries the export line from
 * `exportAge`, with "Export now" one press away: a landed export
 * invalidates the row and the line recomputes.
 *
 * The page stands in a real router and the API client is mocked at its
 * module boundary (the workbench suite's own pattern); the export itself
 * goes out through `fetch`, so the flip case scripts that global — the
 * requests' truth is the backend and E2E suites'.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { t } from "@shell/lib/i18n";
import { formatNumber } from "@shell/lib/format";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";
import { formatRelative } from "@shell/lib/time";

vi.mock("@shell/lib/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

import { client, type Novel } from "@shell/lib/api/client";

import { NovelsPage } from "./NovelsPage";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

const NOVEL_ID = "3d9f0b64-1c2e-4f5a-9b7c-8a1d2e3f4a5b";

/** The card's novel, mutable on purpose: the writes below land on the very
 *  row the next read answers with, the way the server would. */
function shelfNovel(overrides: Partial<Novel> = {}): Novel {
  return {
    id: NOVEL_ID,
    title: "Das Zählwerk",
    author: null,
    blurb: null,
    genre: null,
    language: null,
    chapter_count: 3,
    word_count: 1200,
    created_at: "2026-11-01T09:00:00Z",
    updated_at: "2026-11-02T09:00:00Z",
    last_exported_at: null,
    ...overrides,
  };
}

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The shelf's answers: the gate and the locale beside the list, the row
 *  under its own key (the delete dialog reads it through Query), and the
 *  knowledge list it opens with. The row answers with a COPY on every
 *  read — the way the server would — so a mutation of the fixture reaches
 *  the cache only through a refetch, never by reference. */
function mockShelf(novel: Novel, entities: unknown[] = []): void {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") return { data: { locale: null }, response: ok() };
    if (path === "/api/setup/status") return { data: { complete: true }, response: ok() };
    if (path === "/api/writing/novels") return { data: [novel], response: ok() };
    if (path === "/api/writing/novels/{novel_id}") {
      return { data: { ...novel }, response: ok() };
    }
    if (path === "/api/knowledge/novels/{novel_id}/entities") {
      return { data: entities, response: ok() };
    }
    throw new Error(`unexpected GET ${path}`);
  });
}

/** A PATCH that lands on the mutable row: the next read answers with the
 *  change, the way the server's commit would. */
function mockUpdate(novel: Novel): void {
  api.PATCH.mockImplementation(
    async (
      _path: string,
      init: { body: Record<string, string | null> },
    ): Promise<{ data: Novel; response: Response }> => {
      Object.assign(novel, init.body, { updated_at: new Date().toISOString() });
      return { data: { ...novel }, response: ok() };
    },
  );
}

/** A second book for the composition tests: its own id and title, so the
 *  two cards can never be confused, and its own touch time, so the hero
 *  has a fact to derive from. */
function secondNovel(overrides: Partial<Novel> = {}): Novel {
  return shelfNovel({
    id: "6e1f2a90-3b4c-4d5e-8f9a-0b1c2d3e4f5a",
    title: "Die Halligen",
    chapter_count: 5,
    word_count: 1000,
    updated_at: "2026-11-01T09:00:00Z",
    ...overrides,
  });
}

/** The shelf's answers for a list of novels: the drafted page derives its
 *  metrics and its hero from the whole list, so the composition tests need
 *  more than one row standing. */
function mockShelfList(novels: Novel[]): void {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") return { data: { locale: null }, response: ok() };
    if (path === "/api/setup/status") return { data: { complete: true }, response: ok() };
    if (path === "/api/writing/novels") {
      return { data: novels.map((novel) => ({ ...novel })), response: ok() };
    }
    if (path === "/api/writing/novels/{novel_id}") {
      const row = novels.find((novel) => novel.id === NOVEL_ID) ?? novels[0];
      return { data: { ...row }, response: ok() };
    }
    if (path === "/api/knowledge/novels/{novel_id}/entities") {
      return { data: [], response: ok() };
    }
    throw new Error(`unexpected GET ${path}`);
  });
}

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: NovelsPage,
});

function renderShelf() {
  const router = createRouter({
    routeTree: rootRoute.addChildren([homeRoute]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("the shelf's card actions", () => {
  /** The card's menu trigger: named for the book it acts on, the runhead
   *  menu's own convention — found, not got, because the shelf's gate
   *  settles after the render. */
  async function cardMenu(title: string): Promise<HTMLElement> {
    return screen.findByRole("button", { name: t("novels.actionsFor", { title }) });
  }

  /** The card's link by its title: the card's whole text is its accessible
   *  name, so the title is the leading edge, not the whole of it. The
   *  predicate still takes the whole title, so "Das" never matches "Das
   *  Zählwerk". */
  function cardLink(title: string): Promise<HTMLElement> {
    return screen.findByRole("link", {
      name: (name: string) => name === title || name.startsWith(`${title} `),
    });
  }

  it("the_card_menu_offers_details_export_and_delete", { timeout: 10_000 }, async () => {
    const novel = shelfNovel();
    mockShelf(novel);
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    expect(await cardLink(novel.title)).toBeTruthy();

    // The card's three deeds live in one menu, behind the drafted
    // more_horiz trigger: the shelf stays a grid of faces, and the actions
    // are one press away without covering it.
    await user.click(await cardMenu(novel.title));
    expect(screen.getByRole("menuitem", { name: t("novels.details") })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: t("shelf.export") })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: t("novels.delete") })).toBeTruthy();
    // Only the three: nothing else grew into the card's menu.
    expect(screen.getAllByRole("menuitem")).toHaveLength(3);
    await user.keyboard("{Escape}");
  });

  it("details_saves_all_five_fields", { timeout: 10_000 }, async () => {
    const novel = shelfNovel();
    mockShelf(novel);
    mockUpdate(novel);
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    await user.click(await cardMenu(novel.title));
    await user.click(screen.getByRole("menuitem", { name: t("novels.details") }));
    const dialog = await screen.findByRole("dialog");

    // The five fields the book carries, prefilled with the row's own truth.
    const title = within(dialog).getByLabelText(t("novels.titleLabel")) as HTMLInputElement;
    const author = within(dialog).getByLabelText(t("novels.author")) as HTMLInputElement;
    const genre = within(dialog).getByLabelText(t("novels.genre")) as HTMLInputElement;
    const language = within(dialog).getByLabelText(t("novels.language")) as HTMLInputElement;
    const blurb = within(dialog).getByLabelText(t("novels.blurb")) as HTMLInputElement;
    expect(title.value).toBe("Das Zählwerk");
    expect(author.value).toBe("");

    await user.clear(title);
    await user.type(title, "Das neue Zählwerk");
    await user.type(author, "Die Autorin");
    await user.type(genre, "Fantasy");
    await user.type(language, "DE");
    await user.type(blurb, "Ein Klappentext.");
    await user.click(within(dialog).getByRole("button", { name: t("novels.save") }));

    // The PATCH carries exactly the five changed fields — nothing else, no
    // nulls for the ones never touched.
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).toHaveBeenCalledWith("/api/writing/novels/{novel_id}", {
      params: { path: { novel_id: NOVEL_ID } },
      body: {
        title: "Das neue Zählwerk",
        author: "Die Autorin",
        genre: "Fantasy",
        language: "DE",
        blurb: "Ein Klappentext.",
      },
    });

    // Reopened on the saved row, one field cleared is the one field sent:
    // the empty genre is the cleared state (null), and no other field
    // rides along. An untouched submit asks for nothing at all.
    const renameCalls = 1;
    await user.click(await cardMenu("Das neue Zählwerk"));
    await user.click(screen.getByRole("menuitem", { name: t("novels.details") }));
    const again = await screen.findByRole("dialog");
    const genreAgain = within(again).getByLabelText(t("novels.genre")) as HTMLInputElement;
    await user.clear(genreAgain);
    await user.click(within(again).getByRole("button", { name: t("novels.save") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).toHaveBeenCalledTimes(renameCalls + 1);
    expect(api.PATCH).toHaveBeenLastCalledWith("/api/writing/novels/{novel_id}", {
      params: { path: { novel_id: NOVEL_ID } },
      body: { genre: null },
    });

    await user.click(await cardMenu("Das neue Zählwerk"));
    await user.click(screen.getByRole("menuitem", { name: t("novels.details") }));
    const third = await screen.findByRole("dialog");
    await user.click(within(third).getByRole("button", { name: t("novels.save") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).toHaveBeenCalledTimes(renameCalls + 1);
  });

  it("an_empty_title_is_refused_by_name", { timeout: 10_000 }, async () => {
    const novel = shelfNovel();
    mockShelf(novel);
    mockUpdate(novel);
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    await user.click(await cardMenu(novel.title));
    await user.click(screen.getByRole("menuitem", { name: t("novels.details") }));
    const dialog = await screen.findByRole("dialog");
    const title = within(dialog).getByLabelText(t("novels.titleLabel"));
    await user.clear(title);
    await user.click(within(dialog).getByRole("button", { name: t("novels.save") }));

    // The refusal names the field, the dialog stays, and nothing flew.
    expect(within(dialog).getByText(t("novels.titleRequired"))).toBeTruthy();
    expect(api.PATCH).not.toHaveBeenCalled();

    // The mark is derived, not stored: typing an answer lifts it at once.
    await user.type(title, "x");
    expect(within(dialog).queryByText(t("novels.titleRequired"))).toBeNull();
  });

  it("an_invalid_language_is_refused_on_the_field", { timeout: 10_000 }, async () => {
    const novel = shelfNovel({ language: "de" });
    mockShelf(novel);
    mockUpdate(novel);
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    await user.click(await cardMenu(novel.title));
    await user.click(screen.getByRole("menuitem", { name: t("novels.details") }));
    const dialog = await screen.findByRole("dialog");
    const field = () => within(dialog).getByLabelText(t("novels.language"));

    // A word, not a code: the field's own pattern refuses it by name —
    // before the wire, so no request carries it. The refusal is the
    // field's state: the mark and `aria-invalid` both name it.
    await user.type(field(), "deutsch");
    await user.click(within(dialog).getByRole("button", { name: t("novels.save") }));
    expect(within(dialog).getByText(t("novels.languageInvalid"))).toBeTruthy();
    expect(field().getAttribute("aria-invalid")).toBe("true");
    expect(api.PATCH).not.toHaveBeenCalled();

    // The server's own refusal lands on the same field: a 422 naming the
    // language ("invalid language", the router's detail) is the field's
    // error, not the dialog's outage sentence. The value is pattern-valid
    // — only the wire refuses it.
    await user.clear(field());
    await user.type(field(), "en");
    api.PATCH.mockResolvedValueOnce({
      data: undefined,
      error: { detail: "invalid language" },
      response: new Response(null, { status: 422 }),
    });
    await user.click(within(dialog).getByRole("button", { name: t("novels.save") }));
    await waitFor(() =>
      expect(within(dialog).getByText(t("novels.languageInvalid"))).toBeTruthy(),
    );
    expect(within(dialog).queryByText(t("novels.errorUpdate"))).toBeNull();

    // A cleared field is a clear, not a refusal: both marks lift at once
    // (the visible error and `aria-invalid` — an error the save would
    // contradict is a lie), and the save carries exactly the cleared
    // state, `language: null`.
    await user.clear(field());
    expect(within(dialog).queryByText(t("novels.languageInvalid"))).toBeNull();
    expect(field().getAttribute("aria-invalid")).toBeNull();
    await user.click(within(dialog).getByRole("button", { name: t("novels.save") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.PATCH).toHaveBeenLastCalledWith("/api/writing/novels/{novel_id}", {
      params: { path: { novel_id: NOVEL_ID } },
      body: { language: null },
    });
  });

  it("the_delete_dialog_names_chapters_entities_and_that_documents_survive", {
    timeout: 10_000,
  }, async () => {
    const novel = shelfNovel({ chapter_count: 3 });
    // The entities read is the dialog's own ask, and it opens gated: the
    // chapter count is the row's own fact and must not wait behind it.
    let answerEntities: (rows: unknown[]) => void = () => {};
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") return { data: { locale: null }, response: ok() };
      if (path === "/api/setup/status") return { data: { complete: true }, response: ok() };
      if (path === "/api/writing/novels") return { data: [novel], response: ok() };
      if (path === "/api/writing/novels/{novel_id}") {
        return { data: { ...novel }, response: ok() };
      }
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return new Promise((resolve) => {
          answerEntities = (rows) => resolve({ data: rows, response: ok() });
        });
      }
      throw new Error(`unexpected GET ${path}`);
    });
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    await user.click(await cardMenu(novel.title));
    await user.click(screen.getByRole("menuitem", { name: t("novels.delete") }));
    const dialog = await screen.findByRole("dialog");

    // What dies is named at once from the row — the entities ask still on
    // the wire — and what stays with it: the documents are the library's,
    // not the book's. The entity half is absent, not guessed, while it
    // loads: a number the dialog does not have is not a zero.
    expect(
      within(dialog).getByText(t("novels.deleteChapters", { chapters: 3 })),
    ).toBeTruthy();
    expect(within(dialog).getByText(t("novels.deleteDocuments"))).toBeTruthy();
    expect(
      within(dialog).queryByText(t("novels.deleteEntities", { entities: 2 })),
    ).toBeNull();

    // The ask lands: the second half joins the first, both counts the
    // truth now.
    await act(async () => {
      answerEntities([{ id: "e1" }, { id: "e2" }]);
    });
    await waitFor(() =>
      expect(
        within(dialog).getByText(t("novels.deleteEntities", { entities: 2 })),
      ).toBeTruthy(),
    );
    expect(
      within(dialog).getByText(t("novels.deleteChapters", { chapters: 3 })),
    ).toBeTruthy();

    // A dismissed ask deletes nothing.
    await user.click(within(dialog).getByRole("button", { name: t("novels.cancel") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.DELETE).not.toHaveBeenCalled();

    // One chapter is still a sentence: the verb lives inside the plural's
    // branches, so the singular agrees ("1 chapter is", never "1 chapter
    // are"). The shelf re-renders at a one-chapter book to read it.
    cleanup();
    queryClient.clear();
    mockShelf(shelfNovel({ chapter_count: 1 }));
    renderShelf();
    await user.click(await cardMenu(novel.title));
    await user.click(screen.getByRole("menuitem", { name: t("novels.delete") }));
    const singular = await screen.findByRole("dialog");
    expect(
      within(singular).getByText((content) => content.includes("1 chapter is")),
    ).toBeTruthy();
  });

  it("confirming_the_delete_removes_the_card", { timeout: 10_000 }, async () => {
    const novel = shelfNovel();
    mockShelf(novel);
    let standing = true;
    api.DELETE.mockImplementation(
      async (_path: string, init: { params: { path: { novel_id: string } } }) => {
        if (init.params.path.novel_id !== NOVEL_ID) {
          return { response: new Response(null, { status: 404 }) };
        }
        standing = false;
        return { response: new Response(null, { status: 204 }) };
      },
    );
    // The list answers with the row while it stands and without it once the
    // delete landed — the refetch the mutation's invalidation triggers.
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") return { data: { locale: null }, response: ok() };
      if (path === "/api/setup/status") return { data: { complete: true }, response: ok() };
      if (path === "/api/writing/novels") {
        return { data: standing ? [novel] : [], response: ok() };
      }
      if (path === "/api/writing/novels/{novel_id}") {
        return { data: novel, response: ok() };
      }
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return { data: [], response: ok() };
      }
      throw new Error(`unexpected GET ${path}`);
    });
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    expect(await cardLink(novel.title)).toBeTruthy();

    await user.click(await cardMenu(novel.title));
    await user.click(screen.getByRole("menuitem", { name: t("novels.delete") }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: t("novels.delete") }));

    // The ask flew, the dialog closed, and the shelf's refetch left the
    // empty state — the card is gone, not merely covered.
    expect(api.DELETE).toHaveBeenCalledWith("/api/writing/novels/{novel_id}", {
      params: { path: { novel_id: NOVEL_ID } },
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    // The shelf's refetch left the drafted empty panel — the card is gone,
    // not merely covered.
    await waitFor(() => expect(screen.getByText(t("shelf.empty.title"))).toBeTruthy());
  });

  it("the_delete_dialog_says_never_exported_and_offers_export", {
    timeout: 10_000,
  }, async () => {
    const novel = shelfNovel({ last_exported_at: null });
    mockShelf(novel);
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    await user.click(await cardMenu(novel.title));
    await user.click(screen.getByRole("menuitem", { name: t("novels.delete") }));
    const dialog = await screen.findByRole("dialog");

    // The never-exported truth is the loudest warning a delete can carry,
    // and the way out sits beside it: the export, one press away.
    expect(within(dialog).getByText(t("novels.exportNever"))).toBeTruthy();
    expect(
      within(dialog).getByRole("button", { name: t("novels.exportNow") }),
    ).toBeTruthy();
    await user.click(within(dialog).getByRole("button", { name: t("novels.cancel") }));
  });

  it("a_fresh_export_flips_the_line", { timeout: 10_000 }, async () => {
    const novel = shelfNovel({ last_exported_at: null });
    mockShelf(novel);
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    await user.click(await cardMenu(novel.title));
    await user.click(screen.getByRole("menuitem", { name: t("novels.delete") }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(t("novels.exportNever"))).toBeTruthy();

    // The export's wire is fetch, not the typed client: the stack's answer
    // is the receipt, and the row the flip reads has its stamp set by the
    // same press — the invalidation the export's success owes the row.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        novel.last_exported_at = new Date().toISOString();
        return new Response(JSON.stringify({ path: "/tmp/export", chapters: 3, entities: 0 }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }),
    );

    await user.click(within(dialog).getByRole("button", { name: t("novels.exportNow") }));
    const exportDialog = await screen.findByRole("dialog", {
      name: t("shelf.exportTitle", { title: novel.title }),
    });
    // Path mode is the delete's offer: the folder field stands prefilled.
    expect(
      within(exportDialog).getByLabelText(t("shelf.export.pathLabel")),
    ).toBeTruthy();
    await user.click(
      within(exportDialog).getByRole("button", { name: t("shelf.export.submit") }),
    );
    expect(
      await within(exportDialog).findByText(t("shelf.export.doneHeading")),
    ).toBeTruthy();
    await user.click(
      within(exportDialog).getByRole("button", { name: t("shelf.export.close") }),
    );

    // Back under it, the delete dialog's line has recomputed from the
    // refetched row: the never-exported warning is gone, the fresh truth
    // stands in its place. The row's GET ran twice — the dialog's own
    // first read, then the export's success invalidation — and only that
    // second read could carry the stamp (every read answers with a copy,
    // so the mutation alone reaches nothing the cache holds).
    await waitFor(() =>
      expect(within(dialog).getByText(t("novels.exportFresh"))).toBeTruthy(),
    );
    expect(within(dialog).queryByText(t("novels.exportNever"))).toBeNull();
    const rowReads = api.GET.mock.calls.filter(
      ([path]) => path === "/api/writing/novels/{novel_id}",
    ).length;
    expect(rowReads).toBe(2);
  });
});

describe("the drafted shelf (Task 10)", () => {
  /** The card's link by its title — the full title is the accessible
   *  name's leading edge, so the long-title pin can lean on the same
   *  helper. */
  function cardLink(title: string): Promise<HTMLElement> {
    return screen.findByRole("link", {
      name: (name: string) => name === title || name.startsWith(`${title} `),
    });
  }

  it("every_drafted_section_is_present", { timeout: 10_000 }, async () => {
    mockShelfList([shelfNovel()]);
    renderShelf();

    // The header: eyebrow, page title, subtitle. The eyebrow is the
    // loaded page's own mark — the wait paints it, never the skeleton,
    // which borrows the page's title for its own shape.
    expect(await screen.findByText(t("shelf.eyebrow"))).toBeTruthy();
    expect(screen.getByRole("heading", { name: t("shelf.title") })).toBeTruthy();
    expect(screen.getByText(t("shelf.subtitle"))).toBeTruthy();
    // The metrics strip.
    expect(screen.getByText(t("shelf.metrics.activeProjects"))).toBeTruthy();
    expect(screen.getByText(t("shelf.metrics.totalWords"))).toBeTruthy();
    expect(screen.getByText(t("shelf.metrics.streak"))).toBeTruthy();
    // The hero.
    expect(
      await screen.findByRole("region", { name: t("shelf.hero.active") }),
    ).toBeTruthy();
    // The filter row: search, filter, view toggle.
    expect(screen.getByRole("textbox", { name: t("shelf.searchLabel") })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: t("shelf.filterLabel") })).toBeTruthy();
    expect(screen.getByRole("group", { name: t("shelf.viewLabel") })).toBeTruthy();
    // The grid and the banner.
    expect(screen.getByRole("list")).toBeTruthy();
    expect(await cardLink("Das Zählwerk")).toBeTruthy();
    expect(screen.getByText(t("shelf.banner.weekly"))).toBeTruthy();
  });

  it("the_hero_derives_from_the_last_touched_novel", { timeout: 10_000 }, async () => {
    const older = secondNovel();
    const newer = shelfNovel({
      title: "Der Sturm",
      genre: "Mystery",
      blurb: "Ein Klappentext.",
      chapter_count: 3,
      word_count: 1200,
      updated_at: "2026-11-02T09:00:00Z",
    });
    mockShelfList([older, newer]);
    renderShelf();

    const hero = await screen.findByRole("region", { name: t("shelf.hero.active") });
    // The newest book is the one to continue; an older one never wins.
    // The heading, not the cover's lettering — the tile repeats the name.
    expect(within(hero).getByRole("heading", { name: "Der Sturm" })).toBeTruthy();
    expect(within(hero).queryByText("Die Halligen")).toBeNull();
    // The hero's facts are the row's own: words, chapters, the touch time.
    expect(within(hero).getByText(formatNumber(1200))).toBeTruthy();
    expect(within(hero).getByText("3")).toBeTruthy();
    expect(
      within(hero).getByText(t("novels.lastTouched", { time: formatRelative(newer.updated_at) })),
    ).toBeTruthy();
    // The CTA names the chapter it continues and opens the book it names.
    const door = within(hero).getByRole("link", {
      name: t("shelf.hero.continueChapter", { n: 3 }),
    });
    expect(door.getAttribute("href")).toContain(newer.id);
    // The outline door opens the novel's planning surface, not the editor
    // beside it: the planning landing carries the novel as `?novel=`.
    const outline = within(hero).getByRole("link", { name: t("shelf.hero.outline") });
    expect(outline.getAttribute("href")).toContain("/planning");
    expect(outline.getAttribute("href")).toContain(`novel=${newer.id}`);
  });

  it("the_metrics_derive_from_the_list", { timeout: 10_000 }, async () => {
    mockShelfList([
      shelfNovel({ word_count: 1200, updated_at: "2026-11-02T09:00:00Z" }),
      secondNovel({ word_count: 1000 }),
    ]);
    renderShelf();

    // Two books, their words summed — both numbers the list itself owns.
    expect(await screen.findByText(t("shelf.metrics.novels", { count: 2 }))).toBeTruthy();
    expect(screen.getByText(formatNumber(2200))).toBeTruthy();
  });

  it("interim_fields_render_their_neutral_exactly", { timeout: 10_000 }, async () => {
    mockShelfList([
      shelfNovel({ word_count: 1200, updated_at: "2026-11-02T09:00:00Z" }),
      secondNovel(),
    ]);
    renderShelf();
    await screen.findByRole("region", { name: t("shelf.hero.active") });

    // The streak is "—" until something tracks it — never a guessed number.
    expect(screen.getByText(t("shelf.metrics.streak"))).toBeTruthy();
    expect(screen.getByText(t("shelf.streakNone"))).toBeTruthy();
    // No target exists: no "x / y Wörter" pair and no progress bar anywhere.
    expect(document.body.textContent).not.toContain("60.000");
    expect(document.querySelector("[data-target-bar]")).toBeNull();
    // Every book wears the draft's default pill.
    const pills = screen.getAllByText(t("shelf.statusDraft"));
    expect(pills).toHaveLength(2);
    // The banner's goal is 0, its weekly average 0, its sparkline flat.
    expect(screen.getByText(t("shelf.banner.goal", { count: 0 }))).toBeTruthy();
    expect(screen.getByText(t("shelf.banner.weeklyValue", { count: 0 }))).toBeTruthy();
    expect(
      screen.getByText(t("shelf.banner.goalIdle", { count: 0, remaining: 0 })),
    ).toBeTruthy();
    const sparkline = document.querySelector("[data-sparkline] path");
    expect(sparkline?.getAttribute("d")).toBe("M 0,16 L 120,16");
  });

  it("search_filters_titles", { timeout: 10_000 }, async () => {
    mockShelfList([
      shelfNovel({ title: "Der Sturm", updated_at: "2026-11-02T09:00:00Z" }),
      secondNovel(),
    ]);
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    expect(await cardLink("Der Sturm")).toBeTruthy();
    expect(await cardLink("Die Halligen")).toBeTruthy();

    const search = screen.getByRole("textbox", { name: t("shelf.searchLabel") });
    await user.type(search, "sturm");

    // Only the matching title stands; the match is case-insensitive.
    expect(screen.getByRole("link", { name: /Der Sturm/ })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Die Halligen/ })).toBeNull();

    // Clearing the box brings the whole shelf back.
    await user.clear(search);
    expect(screen.getByRole("link", { name: /Die Halligen/ })).toBeTruthy();
  });

  it("the_toggle_switches_views", { timeout: 10_000 }, async () => {
    mockShelfList([shelfNovel()]);
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    expect(await cardLink("Das Zählwerk")).toBeTruthy();

    // The grid stands; the pressed state says which view is on.
    const grid = screen.getByRole("button", { name: t("shelf.viewGrid") });
    const list = screen.getByRole("button", { name: t("shelf.viewList") });
    expect(grid.getAttribute("aria-pressed")).toBe("true");
    expect(list.getAttribute("aria-pressed")).toBe("false");
    expect(document.querySelector("[data-shelf-card]")).toBeTruthy();
    expect(document.querySelector("[data-shelf-row]")).toBeNull();

    await user.click(list);
    expect(list.getAttribute("aria-pressed")).toBe("true");
    expect(grid.getAttribute("aria-pressed")).toBe("false");
    expect(document.querySelector("[data-shelf-card]")).toBeNull();
    expect(document.querySelector("[data-shelf-row]")).toBeTruthy();
    // The row is still the book: its link opens what the card's did.
    expect(screen.getByRole("link", { name: /Das Zählwerk/ })).toBeTruthy();

    await user.click(grid);
    expect(document.querySelector("[data-shelf-card]")).toBeTruthy();
  });

  it("a_long_title_keeps_its_full_string_in_the_accessible_name", {
    timeout: 10_000,
  }, async () => {
    // The 80-character compound from the E2E suite's own shelf pin: the
    // unbreakable token must wrap, never cost the reader the name.
    const longTitle =
      "Die Geschichte Nordseeinsellichterturmwegesommerblickea und die Küsten im Herbst";
    mockShelfList([
      shelfNovel({ title: longTitle, updated_at: "2026-11-02T09:00:00Z" }),
      secondNovel(),
    ]);
    renderShelf();

    const card = await cardLink(longTitle);
    expect(card.textContent).toContain(longTitle);
    // The visible title wraps rather than clamping: no line-clamp rides it.
    const visible = document.querySelector("[data-shelf-title]");
    expect(visible?.className).not.toMatch(/line-clamp/);
  });

  it("the_empty_state_is_the_drafted_panel", { timeout: 10_000 }, async () => {
    mockShelfList([]);
    renderShelf();

    // The empty shelf is quiet, not dead: the drafted panel names itself,
    // the metrics are the honest zeros, the banner waits for a session,
    // and the doors stand as drafted.
    expect(await screen.findByRole("heading", { name: t("shelf.empty.title") })).toBeTruthy();
    expect(screen.getByText(t("shelf.empty.body"))).toBeTruthy();
    expect(screen.getByText(t("shelf.metrics.novels", { count: 0 }))).toBeTruthy();
    expect(screen.getByText(formatNumber(0))).toBeTruthy();
    expect(screen.getByText(t("shelf.banner.noSession"))).toBeTruthy();
    expect(screen.getByText(t("shelf.banner.ready"))).toBeTruthy();
    // The drafted empty shelf carries the create affordance twice — the
    // header's door and the panel's own CTA — and the import door beside
    // them (`shelf-empty.html` draws the full strip, doors included).
    expect(screen.getByRole("button", { name: t("shelf.import") })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: t("novels.new") })).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: t("shelf.empty.importManuscript") }),
    ).toBeTruthy();
    expect(screen.getByText(t("shelf.empty.formats"))).toBeTruthy();
    // No hero stands over an empty library.
    expect(screen.queryByRole("region", { name: t("shelf.hero.active") })).toBeNull();
  });
});
