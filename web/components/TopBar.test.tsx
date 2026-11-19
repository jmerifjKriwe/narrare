// @vitest-environment jsdom
/**
 * The topbar — the W4 chrome draft's semantic bar (56px) on the shell's
 * tokens: the breadcrumb (the shelf face per tile 7, the book face per the
 * live stage — light wins), the interim save chip, the real word chip, the
 * language chip as the real switcher (D17) and the honestly disabled ⌘K
 * search chip (#882). Driven over a bare router with the API client mocked
 * at its module boundary; the queries and the locale store are real.
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
import { TopBar } from "./TopBar";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

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
  series_title: "Tiefsee-Chroniken",
  series_volume: 1,
  updated_at: "2026-11-14T10:00:00Z",
});
const WINTERHAUS = novelRow({
  id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  title: "Winterhaus",
  word_count: 1200,
  updated_at: "2026-11-10T10:00:00Z",
});
const ARCHIVED = novelRow({
  id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
  title: "Archivbuch",
  word_count: 9000,
  archived_at: "2026-11-12T08:00:00Z",
  updated_at: "2026-11-15T10:00:00Z",
});
const ROWS = [DEAD_SIGNAL, WINTERHAUS, ARCHIVED];

let novelsAnswer: () => Promise<{ data?: unknown; response: Response }>;

function scriptApi() {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return {
        data: { locale: "de", theme: null, author_name: null, email: null },
        response: ok(),
      };
    }
    if (path === "/api/writing/novels") return novelsAnswer();
    throw new Error(`unexpected request: ${path}`);
  });
  api.PATCH.mockImplementation(async (path: string, init?: { body?: { locale?: string } }) => {
    if (path === "/api/settings") {
      return { data: { locale: init?.body?.locale ?? null, theme: null }, response: ok() };
    }
    throw new Error(`unexpected request: ${path}`);
  });
}

const testRoot = createRootRoute({ component: () => <Outlet /> });
const homeRoute = createRoute({
  getParentRoute: () => testRoot,
  path: "/",
  component: () => <TopBar />,
});
const bookRoute = createRoute({
  getParentRoute: () => testRoot,
  // The real workspace route's id (W4 Task 11): the chrome resolves the
  // active book from this route's novelId param via the generated leaf.
  path: "/novels/$novelId",
  component: () => <TopBar />,
});

function renderTopBar(path = "/") {
  const router = createRouter({
    routeTree: testRoot.addChildren([homeRoute, bookRoute]),
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
  scriptApi();
  localStorage.clear();
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  applyLocale("de");
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  applyLocale(null);
  localStorage.clear();
  setSaveStatus("idle");
});

describe("the topbar — the shelf face (tile 7)", () => {
  it("breadcrumbs Atelier / Das Bücherregal, the root linking home", async () => {
    renderTopBar("/");
    const root = await screen.findByRole("link", { name: de["shell.topbar.atelier"] });
    expect(root.getAttribute("href")).toBe("/");
    expect(screen.getByText(de["shell.topbar.shelf"])).toBeTruthy();
  });

  it("the word chip is the real total over the active population — archived words stay out", async () => {
    renderTopBar("/");
    // 3.384 + 1.200 = 4.584; the archived 9.000 never joins the sum.
    expect(await screen.findByText(t("shell.topbar.wordsTotal", { count: 4584 }))).toBeTruthy();
  });

  it("an unreachable list answers the family's dash, never an invented zero", async () => {
    novelsAnswer = async () => ({ data: undefined, response: new Response(null, { status: 503 }) });
    renderTopBar("/");
    expect(await screen.findByText("—")).toBeTruthy();
  });
});

describe("the topbar — the book face (the live stage)", () => {
  it("breadcrumbs Manuscripts / <active book> with the book's own word count", async () => {
    renderTopBar("/novels/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    const root = await screen.findByRole("link", { name: de["shell.topbar.manuscripts"] });
    expect(root.getAttribute("href")).toBe("/");
    expect(await screen.findByText("Dead Signal")).toBeTruthy();
    expect(screen.getByText(t("shell.topbar.words", { count: 3384 }))).toBeTruthy();
  });

  it("the volume chip stands only when the book belongs to a series with a volume", async () => {
    renderTopBar("/novels/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    expect(await screen.findByText(t("shell.topbar.volume", { volume: 1 }))).toBeTruthy();
    cleanup();
    queryClient.clear();
    novelsAnswer = async () => ({ data: [WINTERHAUS], response: ok() });
    renderTopBar("/novels/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
    await screen.findByText("Winterhaus");
    expect(screen.queryByText(/Band/)).toBeNull();
  });
});

describe("the topbar — save, search, language", () => {
  it("the save chip rests at Gespeichert — the idle/saved green face", async () => {
    renderTopBar("/");
    expect(await screen.findByText(de["shell.rail.saved"])).toBeTruthy();
  });

  it("the save chip speaks the live owner's three faces (tile 3)", async () => {
    renderTopBar("/");
    expect(await screen.findByText(de["shell.rail.saved"])).toBeTruthy();
    // Engaged: the amber face, the honest sub-label as the tooltip.
    act(() => setSaveStatus("saving"));
    expect(await screen.findByText(de["shell.rail.saving"])).toBeTruthy();
    expect(screen.queryByText(de["shell.rail.saved"])).toBeNull();
    expect(screen.getByTitle(de["shell.rail.saving.note"])).toBeTruthy();
    // Refused: the red face.
    act(() => setSaveStatus("failed"));
    expect(await screen.findByText(de["shell.rail.failed"])).toBeTruthy();
    expect(screen.getByTitle(de["shell.rail.failed.note"])).toBeTruthy();
    // A landed write rests green again.
    act(() => setSaveStatus("saved"));
    expect(await screen.findByText(de["shell.rail.saved"])).toBeTruthy();
  });

  it("the ⌘K search chip is honestly disabled with the palette note (#882)", async () => {
    renderTopBar("/");
    const search = await screen.findByRole("button", { name: `${de["shell.topbar.search"]} ⌘K` });
    expect(search.hasAttribute("disabled")).toBe(true);
    expect(search.textContent).toContain("⌘K");
    // The drafted tooltip names the reason, and the description carries it
    // to assistive tech even while the tooltip waits for hover.
    const noteId = search.getAttribute("aria-describedby");
    expect(noteId).toBeTruthy();
    expect(document.getElementById(noteId as string)?.textContent).toBe(
      de["shell.topbar.search.note"],
    );
  });

  it("the interim ⌘K chip folds away below sm — the bar fits phone widths (#911)", async () => {
    renderTopBar("/");
    const search = await screen.findByRole("button", { name: `${de["shell.topbar.search"]} ⌘K` });
    // jsdom lays out nothing, so the pin holds the mechanism — the chip is
    // display:none below the sm breakpoint and back at sm — while the live
    // capture at 390px is the behavioral proof of the width itself.
    const chip = search.closest("div") as HTMLElement;
    expect(chip.classList.contains("hidden")).toBe(true);
    expect(chip.classList.contains("sm:block")).toBe(true);
    // The real controls never fold: the language switcher stays mounted at
    // every width (so does the word chip beside it).
    const language = await screen.findByRole("button", { name: /Sprache/ });
    expect(language.classList.contains("hidden")).toBe(false);
  });

  it("the language chip is the real switcher — a choice PATCHes the row and speaks it", async () => {
    renderTopBar("/");
    const chip = await screen.findByRole("button", { name: /Sprache/ });
    expect(chip.textContent).toContain("DE (Deutsch)");
    fireEvent.click(chip);
    const menu = await screen.findByRole("menu", { name: de["shell.language"] });
    fireEvent.click(within(menu).getAllByRole("menuitemradio")[1]);
    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Language/ }).textContent).toContain("EN (English)"),
    );
  });
});
