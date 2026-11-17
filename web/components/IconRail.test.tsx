// @vitest-environment jsdom
/**
 * The icon rail — the W4 chrome draft (chrome-rail-topbar, light face wins)
 * ported onto the shell's tokens: the brand head, the book switcher with
 * its real novels menu, the nav (Bücherregal live, the four later-wave
 * doors honestly disabled), and the foot (interim sync dot, the real
 * tri-state theme toggle, the user block with its author_name → email
 * fallback and no tier). Driven over a bare router with the API client
 * mocked at its module boundary — the queries, the theme module and the
 * locale store are real.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

import { client, type Novel } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { t } from "@shell/lib/i18n";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";
import { setSaveStatus } from "@shell/lib/saveStatus";
import { applyTheme } from "@shell/lib/theme";
import { IconRail } from "./IconRail";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** A novel row as the API answers it. */
function novelRow(overrides: Partial<Novel> & { id: string; title: string }): Novel {
  return {
    genre: null,
    blurb: null,
    author: null,
    language: null,
    chapter_count: 0,
    word_count: 0,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-10T10:00:00Z",
    last_exported_at: null,
    status: null,
    series_title: null,
    series_volume: null,
    archived_at: null,
    target_words: null,
    ...overrides,
  };
}

const DEAD_SIGNAL = novelRow({
  id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  title: "Dead Signal",
  genre: "Science Fiction",
  word_count: 3384,
  chapter_count: 3,
  target_words: 65000,
  status: "draft",
  series_title: "Tiefsee-Chroniken",
  series_volume: 1,
  updated_at: "2026-11-14T10:00:00Z",
});
const WINTERHAUS = novelRow({
  id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  title: "Winterhaus",
  word_count: 1200,
  chapter_count: 2,
  updated_at: "2026-11-10T10:00:00Z",
});
const ARCHIVED = novelRow({
  id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
  title: "Archivbuch",
  archived_at: "2026-11-12T08:00:00Z",
  updated_at: "2026-11-15T10:00:00Z",
});
const ROWS = [DEAD_SIGNAL, WINTERHAUS, ARCHIVED];

let novelsAnswer: () => Promise<{ data?: unknown; response: Response }>;
let authorName: string | null;
let email: string | null;
let storedTheme: string | null;

function scriptApi() {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return {
        data: { locale: "de", theme: storedTheme, author_name: authorName, email },
        response: ok(),
      };
    }
    if (path === "/api/writing/novels") return novelsAnswer();
    throw new Error(`unexpected request: ${path}`);
  });
  api.PATCH.mockImplementation(async (path: string, init?: { body?: { theme?: string | null } }) => {
    if (path === "/api/settings/theme") {
      storedTheme = init?.body?.theme ?? null;
      return { data: { theme: storedTheme }, response: ok() };
    }
    throw new Error(`unexpected request: ${path}`);
  });
}

/** A bare router: the rail under test, a home route for its links, and no
 *  shell chrome around it — this file pins the rail itself. */
const testRoot = createRootRoute({ component: () => <Outlet /> });
const homeRoute = createRoute({
  getParentRoute: () => testRoot,
  path: "/",
  component: () => (
    <>
      <p>home</p>
      <IconRail />
    </>
  ),
});
const railRoute = createRoute({
  getParentRoute: () => testRoot,
  path: "/rail-test",
  component: () => <IconRail />,
});
/** The workspace route's harness face (W4 Task 11): the rail's editor door
 *  and switcher rows navigate here; the page itself is the capability's. */
const novelRoute = createRoute({
  getParentRoute: () => testRoot,
  path: "/novels/$novelId",
  component: () => (
    <>
      <p>workspace</p>
      <IconRail />
    </>
  ),
});

function renderRail(path = "/rail-test") {
  const router = createRouter({
    routeTree: testRoot.addChildren([homeRoute, railRoute, novelRoute]),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

const de = catalogs.de;

beforeEach(() => {
  novelsAnswer = async () => ({ data: ROWS, response: ok() });
  authorName = "H. Calder";
  email = "h.calder@station7.de";
  storedTheme = null;
  scriptApi();
  localStorage.clear();
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  applyLocale("de");
  applyTheme(null);
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  applyLocale(null);
  applyTheme(null);
  localStorage.clear();
  setSaveStatus("idle");
});

describe("the rail — brand and book switcher", () => {
  it("the brand head names the atelier and links home", async () => {
    renderRail();
    const brand = await screen.findByRole("link", { name: de["app.title"] });
    expect(brand.getAttribute("href")).toBe("/");
    expect(brand.textContent).toContain("N");
    expect(screen.getByText(de["shell.brand.tagline"])).toBeTruthy();
  });

  it("the switcher chip names the active book — the latest-edited unarchived", async () => {
    renderRail();
    // The archived row is the newest, but archived books never lead. The
    // cover monogram rides the name with the title (WCAG 2.5.3).
    const trigger = await screen.findByRole("button", {
      name: t("shell.rail.switcher.named", { title: "DS Dead Signal" }),
    });
    // The cover chip wears the cover system's monogram.
    expect(trigger.textContent).toContain("DS");
    expect(trigger.textContent).toContain("Dead Signal");
    expect(trigger.getAttribute("aria-haspopup")).toBe("menu");
  });

  it("the menu lists the real novels with their facts, the count, and the new-book door", async () => {
    const router = renderRail();
    fireEvent.click(await screen.findByRole("button", { name: /Aktives Buch/ }));

    const menu = await screen.findByRole("menu", { name: de["shell.rail.menu.title"] });
    expect(within(menu).getByText(t("shell.rail.menu.count", { count: 2 }))).toBeTruthy();
    // The active book leads the menu's mark; every row opens its book's
    // workspace (W4 Task 11).
    const dead = within(menu).getByRole("menuitem", { name: /Dead Signal/ });
    expect(dead.getAttribute("aria-current")).toBe("true");
    expect(dead.textContent).toContain("Science Fiction");
    expect(dead.textContent).toContain("5 %");
    expect(dead.textContent).toContain(de["writing.shelf.status.draft"]);
    const winter = within(menu).getByRole("menuitem", { name: /Winterhaus/ });
    expect(winter.getAttribute("aria-current")).toBeNull();
    expect(winter.textContent).toContain(t("writing.shelf.chapters", { count: 2 }));
    // The archived book is not a switchable work.
    expect(within(menu).queryByText("Archivbuch")).toBeNull();
    // The draft's new-book action stands; the shelf owns the create dialog.
    expect(within(menu).getByRole("menuitem", { name: de["shell.rail.newBook"] })).toBeTruthy();
    fireEvent.click(winter);
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/novels/${WINTERHAUS.id}`),
    );
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("the menu walks with the arrows, Escape closes and returns focus, an outside press closes", async () => {
    renderRail();
    const trigger = await screen.findByRole("button", { name: /Aktives Buch/ });
    fireEvent.click(trigger);
    const menu = await screen.findByRole("menu");
    const items = within(menu).getAllByRole("menuitem");
    expect(document.activeElement).toBe(items[0]);

    fireEvent.keyDown(items[0], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[1]);
    fireEvent.keyDown(items[1], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[2]);
    // Wrap at the end.
    fireEvent.keyDown(items[2], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[0]);
    fireEvent.keyDown(items[0], { key: "ArrowUp" });
    expect(document.activeElement).toBe(items[2]);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(trigger);

    // An outside press closes without stealing focus.
    fireEvent.click(trigger);
    await screen.findByRole("menu");
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("an unreachable list degrades honestly — no invented book", async () => {
    novelsAnswer = async () => ({ data: undefined, response: new Response(null, { status: 503 }) });
    renderRail();
    const trigger = await screen.findByRole("button", { name: de["shell.rail.switcher"] });
    fireEvent.click(trigger);
    const menu = await screen.findByRole("menu");
    expect(within(menu).getByText(de["shell.rail.menu.unavailable"])).toBeTruthy();
    expect(within(menu).queryByRole("menuitem", { name: /Dead Signal/ })).toBeNull();
  });

  it("an empty library answers the honest empty line and the new-book door", async () => {
    novelsAnswer = async () => ({ data: [], response: ok() });
    const router = renderRail();
    const trigger = await screen.findByRole("button", { name: de["shell.rail.switcher"] });
    fireEvent.click(trigger);
    const menu = await screen.findByRole("menu");
    expect(within(menu).getByText(de["shell.rail.menu.empty"])).toBeTruthy();
    fireEvent.click(within(menu).getByRole("menuitem", { name: de["shell.rail.newBook"] }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });
});

describe("the rail — nav", () => {
  it("Bücherregal links home and wears the active face on /", async () => {
    renderRail("/");
    const shelf = await screen.findByRole("link", { name: de["shell.nav.shelf"] });
    expect(shelf.getAttribute("href")).toBe("/");
    expect(shelf.getAttribute("aria-current")).toBe("page");
  });

  it("Bücherregal is not current away from home", async () => {
    renderRail("/rail-test");
    const shelf = await screen.findByRole("link", { name: de["shell.nav.shelf"] });
    expect(shelf.getAttribute("aria-current")).toBeNull();
  });

  it("the editor door opens the active book's workspace — current on a workspace route", async () => {
    renderRail();
    const editor = await screen.findByRole("link", { name: de["shell.nav.editor"] });
    expect(editor.getAttribute("href")).toBe(`/novels/${DEAD_SIGNAL.id}`);
    expect(editor.getAttribute("aria-current")).toBeNull();
    cleanup();
    renderRail(`/novels/${WINTERHAUS.id}`);
    const current = await screen.findByRole("link", { name: de["shell.nav.editor"] });
    expect(current.getAttribute("aria-current")).toBe("page");
    // The switcher's active book is the route's own, not the hero rule's.
    expect(
      screen.getByRole("button", { name: t("shell.rail.switcher.named", { title: "W Winterhaus" }) }),
    ).toBeTruthy();
  });

  it("with no book standing the editor waits disabled — the three later-wave doors keep their notes", async () => {
    novelsAnswer = async () => ({ data: [], response: ok() });
    renderRail();
    const editor = await screen.findByRole("button", { name: de["shell.nav.editor"] });
    expect(editor.hasAttribute("disabled")).toBe(true);
    expect(editor.getAttribute("title")).toBe(de["shell.nav.editor.note"]);
    for (const [label, note] of [
      [de["shell.nav.knowledge"], de["shell.nav.knowledge.note"]],
      [de["shell.nav.planning"], de["shell.nav.planning.note"]],
      [de["shell.nav.settings"], de["shell.nav.settings.note"]],
    ] as const) {
      const button = screen.getByRole("button", { name: label });
      expect(button.hasAttribute("disabled")).toBe(true);
      expect(button.getAttribute("title")).toBe(note);
    }
  });

  it("the three later-wave doors stay honestly disabled with their notes while books stand", async () => {
    renderRail();
    for (const [label, note] of [
      [de["shell.nav.knowledge"], de["shell.nav.knowledge.note"]],
      [de["shell.nav.planning"], de["shell.nav.planning.note"]],
      [de["shell.nav.settings"], de["shell.nav.settings.note"]],
    ] as const) {
      const button = await screen.findByRole("button", { name: label });
      expect(button.hasAttribute("disabled")).toBe(true);
      expect(button.getAttribute("title")).toBe(note);
    }
  });
});

describe("the rail — foot: sync, theme, user", () => {
  it("the sync dot rests at Gespeichert — the idle/saved green face", async () => {
    renderRail();
    expect(await screen.findByText(de["shell.rail.saved"])).toBeTruthy();
  });

  it("the sync dot speaks the live owner's three faces — one state with the topbar", async () => {
    renderRail();
    expect(await screen.findByText(de["shell.rail.saved"])).toBeTruthy();
    act(() => setSaveStatus("saving"));
    expect(await screen.findByText(de["shell.rail.saving"])).toBeTruthy();
    expect(screen.getByTitle(de["shell.rail.saving.note"])).toBeTruthy();
    act(() => setSaveStatus("failed"));
    expect(await screen.findByText(de["shell.rail.failed"])).toBeTruthy();
    expect(screen.getByTitle(de["shell.rail.failed.note"])).toBeTruthy();
    act(() => setSaveStatus("saved"));
    expect(await screen.findByText(de["shell.rail.saved"])).toBeTruthy();
  });

  it("the theme toggle cycles system → light → dark, applying and PATCHing each step", async () => {
    renderRail();
    const toggle = await screen.findByRole("button", { name: /Erscheinungsbild/ });
    expect(toggle.getAttribute("aria-label")).toBe(
      t("shell.rail.theme", { current: de["shell.theme.system"], next: de["shell.theme.light"] }),
    );

    fireEvent.click(toggle);
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings/theme", { body: { theme: "light" } });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Erscheinungsbild/ }).getAttribute("aria-label")).toBe(
        t("shell.rail.theme", { current: de["shell.theme.light"], next: de["shell.theme.dark"] }),
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: /Erscheinungsbild/ }));
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings/theme", { body: { theme: "dark" } });
    // The row's answer drives the next step — wait for it before clicking.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Erscheinungsbild/ }).getAttribute("aria-label")).toBe(
        t("shell.rail.theme", { current: de["shell.theme.dark"], next: de["shell.theme.system"] }),
      ),
    );

    // The third step hands the choice back to the system.
    fireEvent.click(screen.getByRole("button", { name: /Erscheinungsbild/ }));
    await waitFor(() => expect(document.documentElement.dataset.theme).toBeUndefined());
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings/theme", { body: { theme: null } });
  });

  it("a refused theme write restores the prior appearance", async () => {
    renderRail();
    const toggle = await screen.findByRole("button", { name: /Erscheinungsbild/ });
    api.PATCH.mockResolvedValueOnce({
      error: { detail: "refused" },
      response: new Response(null, { status: 503 }),
    });
    fireEvent.click(toggle);
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    // The optimistic light gave way back to the system's own.
    await waitFor(() => expect(document.documentElement.dataset.theme).toBeUndefined());
  });

  it("the user block names author_name with its initials — no tier", async () => {
    renderRail();
    expect(await screen.findByText("H. Calder")).toBeTruthy();
    expect(screen.getByText("HC")).toBeTruthy();
    expect(screen.queryByText(/Pro|Free|Tier/)).toBeNull();
  });

  it("without an author name the email label answers, initials from the email", async () => {
    authorName = null;
    renderRail();
    expect(await screen.findByText("h.calder@station7.de")).toBeTruthy();
    expect(screen.getByText("HC")).toBeTruthy();
  });

  it("with neither name nor email the block stays an honest profile neutral", async () => {
    authorName = null;
    email = null;
    renderRail();
    expect(await screen.findByText(de["shell.rail.user"])).toBeTruthy();
    expect(screen.queryByText("HC")).toBeNull();
  });
});
