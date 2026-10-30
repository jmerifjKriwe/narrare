// @vitest-environment jsdom
/**
 * The palette is the app's keyboard surface: ⌘K (and Ctrl+K) opens it on any
 * route, Esc closes it and the focus walks back to the opener. Its groups
 * fill from context — with a novel: Chapters, Entities, Docks & pages,
 * Commands; without one, Novels replaces the first two — and typing filters
 * through every catalog, so the words survive a mid-session language switch.
 * A result either navigates (a chapter as `?chapter=`, an entity as `?entity=`
 * on the dock, a novel as an ordinary jump) or runs a command (the new
 * chapter's POST and invalidation; the export dialog through the modal slot,
 * whose lazy chunk loads under the palette's own Suspense boundary). Nothing
 * here is persisted, and the flush gate belongs to the workspace: the palette
 * only navigates.
 *
 * The shell is mounted for real — the root route carries the ⌘K listener and
 * the palette — over stub capability routes: the palette is the subject, the
 * pages behind its jumps are not. The API client is mocked at its module
 * boundary, like the workbench's own tests.
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

import { client } from "../lib/api/client";
import { t } from "../lib/i18n";
import { applyLocale } from "../lib/locale";
import { queryClient } from "../lib/query";
import { rootRoute } from "../routes/__root";

vi.mock("../lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

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
const NEW_CHAPTER_ID = "9c4e37a1-5b8d-4c2f-8a16-3e7f9d2c4b05";
const CHAPTERS = [
  {
    id: CHAPTER_ID,
    novel_id: NOVEL_ID,
    title: "Der Anfang",
    body: "",
    position: 0,
    created_at: "2026-10-30T09:00:00Z",
    updated_at: "2026-10-30T09:00:00Z",
  },
];
const ENTITY_ID = "aa00b163-2c8f-4a6f-9e07-6f5f2c8d1b64";
const ENTITIES = [
  {
    id: ENTITY_ID,
    novel_id: NOVEL_ID,
    name: "Meister Lampe",
    aliases: ["Lampe", "der Hase"],
    tags: ["Figur"],
    type: "character",
    content: "",
    created_at: "2026-10-30T09:00:00Z",
    updated_at: "2026-10-30T09:00:00Z",
  },
];

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The answers of an open book: the shell's locale gate, the book's rows, its
 *  chapters and its entities — whatever the palette's groups ask for. */
function mockWorkspace(): void {
  api.GET.mockImplementation(
    async (path: string, init?: { params?: { path?: { novel_id?: string } } }) => {
      const novelId = init?.params?.path?.novel_id;
      switch (path) {
        case "/api/settings":
          return { data: { locale: null }, response: ok() };
        case "/api/writing/novels":
          return { data: [NOVEL], response: ok() };
        case "/api/writing/novels/{novel_id}":
          return { data: novelId === NOVEL_ID ? NOVEL : undefined, response: ok() };
        case "/api/writing/novels/{novel_id}/chapters":
          return { data: novelId === NOVEL_ID ? CHAPTERS : [], response: ok() };
        case "/api/knowledge/novels/{novel_id}/entities":
          return { data: novelId === NOVEL_ID ? ENTITIES : [], response: ok() };
        default:
          throw new Error(`unexpected GET ${path}`);
      }
    },
  );
}

/** The answers of a route outside any book: the locale gate and the shelf. */
function mockBare(): void {
  api.GET.mockImplementation(async (path: string) => {
    switch (path) {
      case "/api/settings":
        return { data: { locale: null }, response: ok() };
      case "/api/writing/novels":
        return { data: [NOVEL], response: ok() };
      default:
        throw new Error(`unexpected GET ${path}`);
    }
  });
}

// Stub capability routes: destinations the palette can jump to, with none of
// the pages' own machinery — the palette is the subject here.
function stubRoutes(root: typeof rootRoute) {
  const home = createRoute({
    getParentRoute: () => root,
    path: "/",
    component: () => <p>home</p>,
  });
  const novel = createRoute({
    getParentRoute: () => root,
    path: "/novels/$id",
    component: () => <p>workbench</p>,
  });
  const wissen = createRoute({
    getParentRoute: () => novel,
    path: "wissen",
    component: () => <p>wissen</p>,
  });
  const settings = createRoute({
    getParentRoute: () => root,
    path: "/settings",
    component: () => <p>settings</p>,
  });
  const prompts = createRoute({
    getParentRoute: () => root,
    path: "/settings/prompts",
    component: () => <p>prompts</p>,
  });
  return [home, novel, wissen, settings, prompts];
}

function renderAt(path: string) {
  const router = createRouter({
    routeTree: rootRoute.addChildren(stubRoutes(rootRoute)),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

/** The keyboard opens the palette wherever the focus sits — the shell's
 *  listener reads the window, no page participates. The press waits for the
 *  shell's own mount: the pre-paint gate holds the shell back while the
 *  locale read answers, and the listener attaches with it. */
async function openPalette(): Promise<void> {
  await screen.findByRole("link", { name: t("chat.heading") });
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
  await screen.findByRole("dialog");
}

async function searchBox(): Promise<HTMLInputElement> {
  const dialog = await screen.findByRole("dialog");
  const input = within(dialog).getByRole("textbox") as HTMLInputElement;
  return input;
}

/** A row of the open palette, once its render has settled — the groups fill
 *  from Query, so a row can land a tick after the dialog itself. */
async function paletteRow(name: string): Promise<HTMLElement> {
  const dialog = await screen.findByRole("dialog");
  return within(dialog).findByRole("button", { name });
}

/** A group of the open palette, likewise. */
async function paletteGroup(name: string): Promise<HTMLElement> {
  const dialog = await screen.findByRole("dialog");
  return within(dialog).findByRole("group", { name });
}

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  // The locale is global state; the tests that switch it must not leak.
  applyLocale(null);
});

describe("the palette's keyboard contract", () => {
  it("opens with ⌘K and with Ctrl+K, closes with Esc, and the focus returns to the opener", async () => {
    mockBare();
    renderAt("/");
    // The opener is an ordinary page element — the top bar's first link.
    const opener = await screen.findByRole("link", { name: t("chat.heading") });
    opener.focus();

    await openPalette();
    const dialog = screen.getByRole("dialog");
    // The shortcuts are named here, in one place — the §11 row.
    expect(dialog.textContent).toContain(t("workspace.shortcutHints"));

    // Ctrl+K is the same key on the other platforms, and it closes again —
    // every close returns the focus, so the next press is captured from the
    // same place.
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener));

    // Open once more; Esc closes and the focus walks back to the opener —
    // settled with the shell's own effects, not at the instant the overlay
    // leaves the DOM.
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
    await screen.findByRole("dialog");
    const user = userEvent.setup();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });
});

describe("the groups fill from context", () => {
  it("with a novel: Chapters, Entities, Docks & pages, Commands — the blank query shows every row", async () => {
    mockWorkspace();
    renderAt(`/novels/${NOVEL_ID}`);
    await openPalette();

    for (const label of [
      t("palette.chapters"),
      t("palette.entities"),
      t("palette.pages"),
      t("palette.commands"),
    ]) {
      expect(await paletteGroup(label), label).toBeTruthy();
    }
    // Blank query: everything the context offers is on the list.
    expect(await paletteRow("Der Anfang")).toBeTruthy();
    expect(await paletteRow("Meister Lampe")).toBeTruthy();
    const pages = await paletteGroup(t("palette.pages"));
    // The dock and the app page carry the same catalog word by data — both
    // registries name their rows "Chat" and "Knowledge" — so the group
    // holds both rows, counted, not picked apart by name.
    expect(within(pages).getAllByRole("button", { name: t("knowledge.dockTitle") }).length).toBe(2);
    expect(within(pages).getAllByRole("button", { name: t("chat.heading") }).length).toBe(2);
    const commands = await paletteGroup(t("palette.commands"));
    expect(within(commands).getByRole("button", { name: t("commands.openSettings") })).toBeTruthy();
    expect(within(commands).getByRole("button", { name: t("commands.openPrompts") })).toBeTruthy();
    expect(within(commands).getByRole("button", { name: t("commands.openWissenDock") })).toBeTruthy();
    expect(within(commands).getByRole("button", { name: t("commands.newChapter") })).toBeTruthy();
    expect(within(commands).getByRole("button", { name: t("commands.exportNovel") })).toBeTruthy();
  });

  it("without a novel: Novels replaces the first two, and the novel-bound rows go off", async () => {
    mockBare();
    renderAt("/");
    await openPalette();

    expect(await paletteGroup(t("palette.novels"))).toBeTruthy();
    expect(await paletteRow(NOVEL.title)).toBeTruthy();
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByRole("group", { name: t("palette.chapters") })).toBeNull();
    expect(within(dialog).queryByRole("group", { name: t("palette.entities") })).toBeNull();
    // The dock and the novel-bound commands live at a novel: without one
    // they are off, not broken. The pages group keeps the app-wide pages —
    // one "Chat", one "Knowledge" — where the doubled rows of an open
    // workspace would have been the docks.
    const pages = await paletteGroup(t("palette.pages"));
    expect(within(pages).getAllByRole("button", { name: t("knowledge.dockTitle") }).length).toBe(1);
    expect(within(pages).getAllByRole("button", { name: t("chat.heading") }).length).toBe(1);
    const commands = await paletteGroup(t("palette.commands"));
    expect(within(commands).queryByRole("button", { name: t("commands.openWissenDock") })).toBeNull();
    expect(within(commands).queryByRole("button", { name: t("commands.newChapter") })).toBeNull();
    expect(within(commands).queryByRole("button", { name: t("commands.exportNovel") })).toBeNull();
    expect(within(commands).getByRole("button", { name: t("commands.openSettings") })).toBeTruthy();
  });

  it("a novel result jumps to the book — the palette steps aside", async () => {
    mockBare();
    const router = renderAt("/");
    await openPalette();
    const user = userEvent.setup();
    await user.click(await paletteRow(NOVEL.title));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}`));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});

describe("typing filters", () => {
  it("narrow the rows by their own words, aliases included", async () => {
    mockWorkspace();
    renderAt(`/novels/${NOVEL_ID}`);
    await openPalette();
    const user = userEvent.setup();
    const input = await searchBox();

    // The chapter's own title, diacritics-free and case-free.
    await user.type(input, "anfang");
    expect(await paletteRow("Der Anfang")).toBeTruthy();
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByRole("button", { name: "Meister Lampe" })).toBeNull();

    // An entity answers to its alias, not only its name.
    await user.clear(input);
    await user.type(input, "hase");
    expect(await paletteRow("Meister Lampe")).toBeTruthy();
  });

  it("find a command through another locale's word, and keep finding it after a mid-session switch", async () => {
    mockWorkspace();
    renderAt(`/novels/${NOVEL_ID}`);
    await openPalette();
    const user = userEvent.setup();
    const input = await searchBox();

    // The German word, an English UI: the index reads every catalog.
    await user.type(input, "offnen");
    expect(await paletteRow(t("commands.openSettings"))).toBeTruthy();

    // The switch relabels the row — and the English word still finds it,
    // because the switch rebuilt nothing.
    applyLocale("de");
    const germanLabel = "Einstellungen öffnen";
    expect(await paletteRow(germanLabel)).toBeTruthy();
    await user.clear(input);
    await user.type(input, "settings");
    expect(await paletteRow(germanLabel)).toBeTruthy();
  });

  it("name the empty truth when nothing matches", async () => {
    mockWorkspace();
    renderAt(`/novels/${NOVEL_ID}`);
    await openPalette();
    const user = userEvent.setup();
    const input = await searchBox();
    await user.type(input, "worgatsnix");
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(t("palette.noResults"))).toBeTruthy();
  });
});

describe("the deep links", () => {
  it("an entity result lands on the dock with the entity selected", async () => {
    mockWorkspace();
    const router = renderAt(`/novels/${NOVEL_ID}`);
    await openPalette();
    const user = userEvent.setup();
    await user.click(await paletteRow("Meister Lampe"));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/wissen`),
    );
    expect(router.state.location.search).toMatchObject({ entity: ENTITY_ID });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("a chapter result lands in the workspace with the chapter selected", async () => {
    mockWorkspace();
    const router = renderAt(`/novels/${NOVEL_ID}`);
    await openPalette();
    const user = userEvent.setup();
    await user.click(await paletteRow("Der Anfang"));
    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ chapter: CHAPTER_ID }),
    );
    expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}`);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("the commands run", () => {
  it("new-chapter POSTs the empty title, invalidates the chapters key, and navigates to the new ?chapter=", async () => {
    mockWorkspace();
    api.POST.mockResolvedValue({
      data: { id: NEW_CHAPTER_ID, novel_id: NOVEL_ID, title: "", body: "", position: 1, created_at: "2026-10-30T10:00:00Z", updated_at: "2026-10-30T10:00:00Z" },
      response: ok(),
    });
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const router = renderAt(`/novels/${NOVEL_ID}`);
    await openPalette();
    const user = userEvent.setup();
    await user.click(await paletteRow(t("commands.newChapter")));

    // The POST carries the explicit empty title — the placeholder is a
    // display concern, never a stored one — and the invalidations are the
    // cache's asks, not hand-patched arrays: the chapters list the rail and
    // the palette read, and the novels prefix, because the shelf's hero
    // names the last-touched book and a chapter write moves it.
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith("/api/writing/novels/{novel_id}/chapters", {
        params: { path: { novel_id: NOVEL_ID } },
        body: { title: "" },
      }),
    );
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["chapters", NOVEL_ID] }),
    );
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["novels"] }),
    );
    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ chapter: NEW_CHAPTER_ID }),
    );
    invalidate.mockRestore();
  });

  it("export-novel hands the lazy dialog to the modal slot — the palette steps aside, the dialog takes the stage", async () => {
    mockWorkspace();
    renderAt(`/novels/${NOVEL_ID}`);
    await openPalette();
    const user = userEvent.setup();
    await user.click(await paletteRow(t("commands.exportNovel")));

    // The palette closed itself when the slot took over…
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    // …and the lazily imported dialog is on stage, already open.
    const heading = await screen.findByRole("heading", {
      name: t("shelf.exportTitle", { title: NOVEL.title }),
    });
    expect(heading).toBeTruthy();
    expect(screen.getByRole("button", { name: t("shelf.export.submit") })).toBeTruthy();
  });

  it("⌘K refuses to stack the palette over a live dialog", async () => {
    mockWorkspace();
    renderAt(`/novels/${NOVEL_ID}`);
    await openPalette();
    const user = userEvent.setup();
    await user.click(await paletteRow(t("commands.exportNovel")));
    await screen.findByRole("heading", {
      name: t("shelf.exportTitle", { title: NOVEL.title }),
    });
    // The palette stepped aside: the export dialog owns the stage, and it
    // is the only dialog on it.
    expect(screen.queryByRole("dialog", { name: t("palette.title") })).toBeNull();

    // ⌘K during the dialog is refused: opening would stack a second focus
    // trap over the first, typing would drive a page the dialog shadows,
    // and the dialog would survive onto the route the palette jumps to.
    // The settled state, not a race — any wrongly scheduled open lands
    // within act.
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(screen.queryByRole("dialog", { name: t("palette.title") })).toBeNull();
    // The dialog that owned the stage still owns it.
    expect(
      screen.getByRole("heading", { name: t("shelf.exportTitle", { title: NOVEL.title }) }),
    ).toBeTruthy();
  });
});
