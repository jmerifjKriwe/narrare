// @vitest-environment jsdom
/**
 * The shelf's card actions (Task 13): every card carries the action menu —
 * Details and Delete — and the two dialogs behind them. The details dialog
 * is the book's five metadata fields in the new-book form's own refusal
 * style, saving only what the user changed (the PATCH's `model_fields_set`
 * contract mirrored client-side); the language is validated text, refused
 * on its own field by the pattern and by the server's 422 naming it. The
 * delete dialog names what dies — chapters from the card's row, entities
 * from the knowledge list it opens with — says documents survive, and
 * carries the export line from `exportAge`, with "Export now" one press
 * away: a landed export invalidates the row and the line recomputes.
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
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
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
 *  knowledge list it opens with. */
function mockShelf(novel: Novel, entities: unknown[] = []): void {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") return { data: { locale: null }, response: ok() };
    if (path === "/api/setup/status") return { data: { complete: true }, response: ok() };
    if (path === "/api/writing/novels") return { data: [novel], response: ok() };
    if (path === "/api/writing/novels/{novel_id}") return { data: novel, response: ok() };
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
   *  name, so the title is the leading edge, not the whole of it. */
  function cardLink(title: string): Promise<HTMLElement> {
    return screen.findByRole("link", { name: new RegExp(`^${title}\\b`) });
  }

  it("the_card_menu_offers_details_and_delete", { timeout: 10_000 }, async () => {
    const novel = shelfNovel();
    mockShelf(novel);
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    expect(await cardLink(novel.title)).toBeTruthy();

    // The card's two deeds live in one menu: the shelf stays a grid of
    // faces, and the actions are one press away without covering it.
    await user.click(await cardMenu(novel.title));
    expect(screen.getByRole("menuitem", { name: t("novels.details") })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: t("novels.delete") })).toBeTruthy();
    // Only the two: nothing else grew into the card's menu.
    expect(screen.getAllByRole("menuitem")).toHaveLength(2);
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
    const novel = shelfNovel();
    mockShelf(novel);
    mockUpdate(novel);
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    await user.click(await cardMenu(novel.title));
    await user.click(screen.getByRole("menuitem", { name: t("novels.details") }));
    const dialog = await screen.findByRole("dialog");

    // A word, not a code: the field's own pattern refuses it by name —
    // before the wire, so no request carries it.
    await user.type(within(dialog).getByLabelText(t("novels.language")), "deutsch");
    await user.click(within(dialog).getByRole("button", { name: t("novels.save") }));
    expect(within(dialog).getByText(t("novels.languageInvalid"))).toBeTruthy();
    expect(api.PATCH).not.toHaveBeenCalled();

    // The server's own refusal lands on the same field: a 422 naming the
    // language ("invalid language", the router's detail) is the field's
    // error, not the dialog's outage sentence.
    await user.clear(within(dialog).getByLabelText(t("novels.language")));
    await user.type(within(dialog).getByLabelText(t("novels.language")), "de");
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
  });

  it("the_delete_dialog_names_chapters_entities_and_that_documents_survive", {
    timeout: 10_000,
  }, async () => {
    const novel = shelfNovel({ chapter_count: 3 });
    const entities = [{ id: "e1" }, { id: "e2" }];
    mockShelf(novel, entities);
    renderShelf();
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    await user.click(await cardMenu(novel.title));
    await user.click(screen.getByRole("menuitem", { name: t("novels.delete") }));
    const dialog = await screen.findByRole("dialog");

    // What dies, by both counts, and what stays: the documents are the
    // library's, not the book's — the delete says so before it asks.
    expect(
      within(dialog).getByText(
        t("novels.deleteCounts", { chapters: 3, entities: 2 }),
      ),
    ).toBeTruthy();
    expect(within(dialog).getByText(t("novels.deleteDocuments"))).toBeTruthy();

    // A dismissed ask deletes nothing.
    await user.click(within(dialog).getByRole("button", { name: t("novels.cancel") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.DELETE).not.toHaveBeenCalled();
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
    await waitFor(() => expect(screen.getByText(t("novels.empty"))).toBeTruthy());
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
    // stands in its place.
    await waitFor(() =>
      expect(within(dialog).getByText(t("novels.exportFresh"))).toBeTruthy(),
    );
    expect(within(dialog).queryByText(t("novels.exportNever"))).toBeNull();
  });
});
