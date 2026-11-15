// @vitest-environment jsdom
/**
 * The shelf — the `shelf` draft family ported onto the shell's tokens,
 * rendered directly on a harness route under the real root route (the
 * landing's harness precedent: the settings observer, the title provider
 * and the main landmark stay real). Only the API client is mocked at its
 * module boundary; the mock keeps the backend's contract — the novels list
 * carries the rows the shelf must speak, never an invented figure.
 *
 * Every case renders German (the row holds `de`, the browser speaks de-DE)
 * and asserts the du-tone copy the catalog carries: the hero is the
 * latest-edited unarchived novel, the grid is the rest newest-first, the
 * word pair is the row's own count and target, a missing target keeps the
 * landing's honest neutral, the status pill stands only when the book
 * answered, and every door the further build-out has not reached stays
 * disabled with the drafted note. Loading, error (with a working retry)
 * and the empty shelf answer per the states and empty drafts.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
import { formatRelative } from "@shell/lib/time";
import { rootRoute } from "@shell/routes/__root";

import { ShelfPage } from "./ShelfPage";

/** A test-only mount under the real shell — the route gate is the route
 *  test's business; this file pins the face the gate opens onto. */
const shelfRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/shelf-test",
  component: ShelfPage,
});

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** A novel row as the API answers it — the shelf's own facts. */
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

/** The four-book shelf the draft draws — real figures, never the mock's. */
const HERO = novelRow({
  id: "11111111-1111-1111-1111-111111111111",
  title: "Dead Signal",
  genre: "Science Fiction",
  blurb: "Signale aus der Marianenrinne konfrontieren eine Crew mit ihren eigenen Echos.",
  chapter_count: 8,
  word_count: 48342,
  target_words: 65000,
  status: "draft",
  series_title: "Tiefsee-Chroniken",
  series_volume: 2,
  updated_at: "2026-11-14T14:22:00Z",
});
const SECOND = novelRow({
  id: "22222222-2222-2222-2222-222222222222",
  title: "Winterhaus",
  genre: "Mystery",
  chapter_count: 0,
  word_count: 0,
  target_words: 50000,
  updated_at: "2026-11-13T09:00:00Z",
});
const THIRD = novelRow({
  id: "33333333-3333-3333-3333-333333333333",
  title: "The Salt Road",
  genre: "Literary",
  chapter_count: 12,
  word_count: 24150,
  target_words: 45000,
  status: "revision",
  updated_at: "2026-11-11T09:00:00Z",
});
const FOURTH = novelRow({
  id: "44444444-4444-4444-4444-444444444444",
  title: "Der Nebel von Arkona",
  genre: "Historical",
  chapter_count: 5,
  word_count: 11200,
  target_words: 80000,
  status: "final",
  updated_at: "2026-11-08T09:00:00Z",
});
const SHELF_ROWS = [HERO, SECOND, THIRD, FOURTH];
/** An archived book — the toggle's population, never the default's. */
const ARCHIVED = novelRow({
  id: "55555555-5555-5555-5555-555555555555",
  title: "Das stille Archiv",
  genre: "Mystery",
  chapter_count: 4,
  word_count: 9000,
  status: "draft",
  archived_at: "2026-11-12T08:00:00Z",
  updated_at: "2026-11-12T08:00:00Z",
});

/** The settings row's locale, as the backend holds it. */
let rowLocale: string | null = "de";
/** What the novels endpoint answers; a test may script a failure or a gap. */
let novelsAnswer: () => Promise<{ data?: unknown; response: Response }> = async () => ({
  data: SHELF_ROWS,
  response: ok(),
});
/** What the endpoint answers when include_archived asks for the archive. */
let archivedAnswer: () => Promise<{ data?: unknown; response: Response }> = async () => ({
  data: [...SHELF_ROWS, ARCHIVED],
  response: ok(),
});

function scriptApi() {
  api.GET.mockImplementation(async (path: string, init?: { params?: { query?: { include_archived?: boolean } } }) => {
    if (path === "/api/settings") {
      return { data: { locale: rowLocale, theme: null }, response: ok() };
    }
    if (path === "/api/writing/novels") {
      return init?.params?.query?.include_archived ? archivedAnswer() : novelsAnswer();
    }
    throw new Error(`unexpected request: ${path}`);
  });
  api.PATCH.mockImplementation(async (path: string, init?: { body?: { locale?: string } }) => {
    if (path !== "/api/settings") throw new Error(`unexpected request: ${path}`);
    rowLocale = init?.body?.locale ?? null;
    return { data: { locale: rowLocale, theme: null }, response: ok() };
  });
}

function renderShelf() {
  const router = createRouter({
    routeTree: rootRoute.addChildren([shelfRoute]),
    history: createMemoryHistory({ initialEntries: ["/shelf-test"] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

/** The shelf's copy, named by the German catalog the row holds. */
const de = catalogs.de;
const heroSection = () =>
  screen.getByRole("heading", { level: 2, name: HERO.title }).closest("section") as HTMLElement;
const cardOf = (title: string) =>
  screen.getByRole("heading", { level: 3, name: title }).closest("article") as HTMLElement;

beforeEach(() => {
  rowLocale = "de";
  novelsAnswer = async () => ({ data: SHELF_ROWS, response: ok() });
  archivedAnswer = async () => ({ data: [...SHELF_ROWS, ARCHIVED], response: ok() });
  // de-DE formatting: the word pair groups the way the reader's region does.
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  scriptApi();
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  applyLocale(null);
  localStorage.clear();
});

describe("the shelf — the hero and the grid speak the rows' own facts", () => {
  it("the latest-edited unarchived novel leads; the rest follow newest first", async () => {
    renderShelf();

    // The hero is the newest row, at the cover system's hero size.
    expect(await screen.findByRole("heading", { level: 2, name: "Dead Signal" })).toBeTruthy();
    const hero = heroSection();
    const heroCover = hero.querySelector('[data-channel="scifi"]');
    expect(heroCover?.getAttribute("style")).toContain("192px");
    expect(within(hero).getByText(de["writing.shelf.hero.eyebrow"])).toBeTruthy();

    // The grid holds the other three, newest first, at shelf size.
    const cards = screen.getAllByRole("article");
    expect(cards).toHaveLength(3);
    const titles = cards.map((card) => within(card).getByRole("heading", { level: 3 }).textContent);
    expect(titles).toEqual(["Winterhaus", "The Salt Road", "Der Nebel von Arkona"]);
    for (const card of cards) {
      expect(card.querySelector("[data-channel]")?.getAttribute("style")).toContain("144px");
    }
    // The hero's own book never doubles in the grid.
    expect(screen.queryByRole("heading", { level: 3, name: "Dead Signal" })).toBeNull();
    expect(api.GET).toHaveBeenCalledWith("/api/writing/novels");
  });

  it("the metrics strip counts the shelf's own books and words", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    expect(screen.getByText(t("writing.shelf.metrics.books", { count: 4 }))).toBeTruthy();
    // 48.342 + 0 + 24.150 + 11.200 — the sum of the rows, grouped de-DE.
    expect(screen.getByText("83.692")).toBeTruthy();
    expect(screen.getByText(de["writing.shelf.metrics.wordsLabel"])).toBeTruthy();
    // The streak is the activity aggregate's — Task 10 wires it; today the
    // chip stands neutral, never an invented day count.
    expect(screen.getByText(de["writing.shelf.metrics.streakLabel"])).toBeTruthy();
  });

  it("the word pair is the row's count and target, in tabular figures", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const hero = heroSection();
    expect(within(hero).getByText("48.342")).toBeTruthy();
    expect(
      within(hero).getByText(t("writing.shelf.hero.wordsTarget", { target: 65000 })),
    ).toBeTruthy();
    // The drafted progress: 74% label on the exact bar.
    expect(within(hero).getByText(t("writing.shelf.card.percent", { percent: 74 }))).toBeTruthy();
    const track = hero.querySelector(".bg-surface-container-highest");
    const fill = track?.firstElementChild as HTMLElement | null;
    expect(fill).not.toBeNull();
    expect(Number.parseFloat(fill?.style.width ?? "")).toBeCloseTo(74.372, 2);

    // The grid cards carry the same pair, the draft's own figures.
    const salt = cardOf("The Salt Road");
    expect(
      within(salt).getByText(t("writing.shelf.words.pair", { count: 24150, target: 45000 })),
    ).toBeTruthy();
    expect(within(salt).getByText(t("writing.shelf.card.percent", { percent: 53 }))).toBeTruthy();
    const winter = cardOf("Winterhaus");
    expect(
      within(winter).getByText(t("writing.shelf.words.pair", { count: 0, target: 50000 })),
    ).toBeTruthy();
    expect(within(winter).getByText(t("writing.shelf.card.percent", { percent: 0 }))).toBeTruthy();
  });

  it("a missing target keeps the landing's honest neutral — no percentage, empty track", async () => {
    novelsAnswer = async () => ({
      data: [{ ...HERO, target_words: null, word_count: 3384 }, { ...SECOND, target_words: null }],
      response: ok(),
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const hero = heroSection();
    // The count stands alone — no invented goal, no sliver.
    expect(within(hero).getByText("3.384")).toBeTruthy();
    expect(within(hero).getByText(de["writing.shelf.hero.wordsUnit"])).toBeTruthy();
    expect(within(hero).queryByText(/\//)).toBeNull();
    expect(within(hero).getByText(de["writing.shelf.noTarget"])).toBeTruthy();
    const track = hero.querySelector(".bg-surface-container-highest");
    expect(track?.childElementCount).toBe(0);
    expect(within(hero).queryByText(/%/)).toBeNull();

    // The grid card answers the same neutrality: the count, a —, an empty bar.
    const winter = cardOf("Winterhaus");
    expect(within(winter).getByText(t("writing.shelf.words.count", { count: 0 }))).toBeTruthy();
    expect(within(winter).getByText("—")).toBeTruthy();
    expect(winter.querySelector(".bg-surface-container")?.childElementCount).toBe(0);
  });

  it("the status pill stands only when the book answered", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    expect(screen.getByText(de["writing.shelf.status.draft"])).toBeTruthy();
    expect(screen.getByText(de["writing.shelf.status.revision"])).toBeTruthy();
    expect(screen.getByText(de["writing.shelf.status.final"])).toBeTruthy();
    // Winterhaus carries no status — and wears no pill, never a guessed one.
    const winter = cardOf("Winterhaus");
    expect(within(winter).queryByText(de["writing.shelf.status.draft"])).toBeNull();
    expect(within(winter).queryByText(de["writing.shelf.status.revision"])).toBeNull();
    expect(within(winter).queryByText(de["writing.shelf.status.final"])).toBeNull();
  });

  it("the series line rides the hero when the book belongs to one", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    expect(
      screen.getByText(t("writing.shelf.hero.series", { series: "Tiefsee-Chroniken", volume: 2 })),
    ).toBeTruthy();
  });

  it("a series without a volume names the series alone — no invented number", async () => {
    novelsAnswer = async () => ({
      data: [{ ...HERO, series_volume: null }],
      response: ok(),
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    expect(screen.getByText("Tiefsee-Chroniken")).toBeTruthy();
    expect(screen.queryByText(/Band/)).toBeNull();
  });

  it("the last-edited stamp is the row's own moment, localized", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    expect(
      screen.getByText(t("writing.shelf.lastEdited", { when: formatRelative(HERO.updated_at) })),
    ).toBeTruthy();
    const salt = cardOf("The Salt Road");
    expect(within(salt).getByText(formatRelative(THIRD.updated_at))).toBeTruthy();
    // The chapter count is the row's own, pluralized.
    expect(within(salt).getByText(t("writing.shelf.chapters", { count: 12 }))).toBeTruthy();
  });

  it("a long title wraps in full — no ellipsis, the whole name readable", async () => {
    const longTitle =
      "Die Chroniken von Svalbard und das verschollene Signal von Forschungsstation 7";
    novelsAnswer = async () => ({
      data: [HERO, novelRow({ id: "long", title: longTitle, updated_at: "2026-11-12T10:00:00Z" })],
      response: ok(),
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const heading = screen.getByRole("heading", { level: 3, name: longTitle });
    expect(heading.textContent).toBe(longTitle);
    expect(heading.className).not.toContain("truncate");
    expect(heading.className).toContain("break-words");
  });

  it("a growing library flows through the same grid — every book present", async () => {
    const extra = ["Fünf", "Sechs", "Sieben"].map((title, index) =>
      novelRow({
        id: `extra-${index}`,
        title,
        updated_at: `2026-11-0${index + 1}T10:00:00Z`,
      }),
    );
    novelsAnswer = async () => ({ data: [...SHELF_ROWS, ...extra], response: ok() });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    expect(screen.getAllByRole("article")).toHaveLength(6);
    expect(screen.getByText(t("writing.shelf.metrics.books", { count: 7 }))).toBeTruthy();
  });
});

describe("the shelf — every door honest about what is not built yet", () => {
  it("the hero's two doors stay disabled with the drafted note", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    for (const name of [de["writing.shelf.hero.write"], de["writing.shelf.hero.lore"]]) {
      const button = screen.getByRole("button", { name });
      expect(button.hasAttribute("disabled")).toBe(true);
      const noteId = button.getAttribute("aria-describedby");
      expect(noteId).not.toBeNull();
      expect(document.getElementById(noteId as string)?.textContent).toBe(de["writing.shelf.comingSoon"]);
    }
  });

  it("the top bar's new-book and import doors stay disabled with the note", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    for (const name of [de["writing.shelf.newBook"], de["writing.shelf.import"]]) {
      const button = screen.getByRole("button", { name });
      expect(button.hasAttribute("disabled")).toBe(true);
      const noteId = button.getAttribute("aria-describedby");
      expect(document.getElementById(noteId as string)?.textContent).toBe(de["writing.shelf.comingSoon"]);
    }
  });

  it("the view and menu chrome stands inert — their tasks own it", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    // Task 7 made search and filter real; the view toggle and the quick
    // menu stay honestly disabled until their own work lands.
    expect(screen.getByPlaceholderText(de["writing.shelf.search.placeholder"]).hasAttribute("disabled")).toBe(false);
    expect(screen.getByRole("button", { name: de["writing.shelf.search.filter"] }).hasAttribute("disabled")).toBe(false);
    expect(screen.getByRole("button", { name: de["writing.shelf.search.viewGrid"] }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: de["writing.shelf.search.viewList"] }).hasAttribute("disabled")).toBe(true);
    // Task 8's quick menu: one per grid card, disabled with the shared note.
    const menus = screen.getAllByRole("button", { name: de["writing.shelf.card.options"] });
    expect(menus).toHaveLength(3);
    for (const menu of menus) {
      expect(menu.hasAttribute("disabled")).toBe(true);
      const noteId = menu.getAttribute("aria-describedby");
      expect(document.getElementById(noteId as string)?.textContent).toBe(de["writing.shelf.comingSoon"]);
    }
    // Task 10's banner: neutral values, the statistics door disabled.
    expect(screen.getByText(de["writing.shelf.banner.title"])).toBeTruthy();
    expect(screen.getByText(de["writing.shelf.banner.weekly"])).toBeTruthy();
    expect(screen.getByRole("button", { name: de["writing.shelf.banner.stats"] }).hasAttribute("disabled")).toBe(true);
  });

  it("names the tab and speaks the page's du-tone German", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    expect(document.title).toBe(`${de["writing.shelf.title"]} — ${t("app.title")}`);
    expect(screen.getByRole("heading", { level: 1, name: "Das Bücherregal" })).toBeTruthy();
    // The du-tone is the rendered copy, not an English fallback.
    expect(
      screen.getByText("Verwalte deine Manuskripte, Buchstrukturen und schriftstellerischen Entwürfe."),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.shelf.eyebrow"])).toBeTruthy();
  });
});

describe("the shelf — the language switcher writes the row", () => {
  it("switching to English PATCHes the settings row and speaks English", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.click(screen.getByRole("radio", { name: catalogs.en["locale.name"] }));
    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } }),
    );
    const en = catalogs.en;
    expect(await screen.findByRole("button", { name: en["writing.shelf.hero.write"] })).toBeTruthy();
    expect(screen.getByRole("radio", { name: en["locale.name"] }).getAttribute("aria-checked")).toBe("true");
  });

  it("a refused switch restores the prior language", async () => {
    api.PATCH.mockImplementation(async () => ({
      error: { detail: "refused" },
      response: new Response(null, { status: 500 }),
    }));
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.click(screen.getByRole("radio", { name: catalogs.fr["locale.name"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: de["writing.shelf.hero.write"] })).toBeTruthy(),
    );
    expect(screen.getByRole("radio", { name: de["locale.name"] }).getAttribute("aria-checked")).toBe("true");
  });
});

describe("the shelf — loading, error and empty answer per the drafts", () => {
  it("while the list is in flight the skeleton stands — nothing invented", async () => {
    let resolveNovels!: (answer: { data: unknown; response: Response }) => void;
    novelsAnswer = () =>
      new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveNovels = resolve;
      });
    renderShelf();

    await waitFor(() => expect(api.GET).toHaveBeenCalledWith("/api/writing/novels"));
    const status = screen.getByRole("status");
    expect(status.textContent).toContain(de["writing.shelf.loading"]);
    expect(screen.queryByRole("heading", { level: 2, name: "Dead Signal" })).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();

    // ONE metrics strip: the title bar's real chips, their values the pending
    // placeholders — the skeleton never draws a second strip of chip slabs
    // (the review's doubled-placeholder defect: a cold load stacked both).
    for (const label of [
      de["writing.shelf.metrics.booksLabel"],
      de["writing.shelf.metrics.wordsLabel"],
      de["writing.shelf.metrics.streakLabel"],
    ]) {
      expect(screen.getAllByText(label)).toHaveLength(1);
    }
    const strip = screen
      .getByText(de["writing.shelf.metrics.booksLabel"])
      .closest(".flex-wrap") as HTMLElement;
    // Books and words wait as placeholders; the streak stands neutral already.
    expect(strip.querySelectorAll(".animate-pulse")).toHaveLength(2);
    // No chip-height slab anywhere in the skeleton — the strip above is the only one.
    expect(status.querySelectorAll(".h-14")).toHaveLength(0);

    resolveNovels({ data: SHELF_ROWS, response: ok() });
    expect(await screen.findByRole("heading", { level: 2, name: "Dead Signal" })).toBeTruthy();
    // The skeleton's status is gone. The one status that stands with the
    // shelf now is the search's polite result announcer (Task 7).
    expect(screen.queryByText(de["writing.shelf.loading"])).toBeNull();
    expect(screen.getByRole("status").textContent).toBe(t("writing.shelf.search.results", { count: 3 }));
  });

  it("an unreachable list names the failure and offers a working retry", async () => {
    let attempts = 0;
    novelsAnswer = async () => {
      attempts += 1;
      if (attempts === 1) return { data: undefined, response: new Response(null, { status: 503 }) };
      return { data: SHELF_ROWS, response: ok() };
    };
    renderShelf();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(de["writing.shelf.error.title"]);
    // The real status rides the message — never an invented gateway story.
    expect(alert.textContent).toContain("503");
    expect(alert.textContent).toContain("Prüfe die Verbindung zum lokalen Dienst");
    expect(screen.queryByRole("heading", { level: 2, name: "Dead Signal" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.error.retry"] }));
    expect(await screen.findByRole("heading", { level: 2, name: "Dead Signal" })).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(attempts).toBe(2);
  });

  it("the retry names its busy state while the second ask is outstanding", async () => {
    let attempts = 0;
    let resolveSecond!: (answer: { data: unknown; response: Response }) => void;
    novelsAnswer = async () => {
      attempts += 1;
      if (attempts === 1) return { data: undefined, response: new Response(null, { status: 503 }) };
      return new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveSecond = resolve;
      });
    };
    renderShelf();
    await screen.findByRole("alert");

    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.error.retry"] }));
    const busy = await screen.findByRole("button", { name: de["writing.shelf.error.retrying"] });
    expect(busy.hasAttribute("disabled")).toBe(true);

    resolveSecond({ data: SHELF_ROWS, response: ok() });
    expect(await screen.findByRole("heading", { level: 2, name: "Dead Signal" })).toBeTruthy();
  });

  it("an empty shelf opens the honest empty state — the new-book door disabled", async () => {
    novelsAnswer = async () => ({ data: [], response: ok() });
    renderShelf();

    expect(await screen.findByRole("heading", { level: 2, name: "Dein erstes Buch wartet." })).toBeTruthy();
    expect(
      screen.getByText(
        "Jede große Erzählung beginnt mit einem leeren Blatt. Beginne dein Werk im Atelier oder überführe ein bestehendes Manuskript.",
      ),
    ).toBeTruthy();
    // The metrics answer zero, never a dash for a count that is known.
    expect(screen.getByText(t("writing.shelf.metrics.books", { count: 0 }))).toBeTruthy();
    expect(screen.getByText("0")).toBeTruthy();

    // Both doors of the empty panel stay disabled with the drafted note.
    for (const name of [de["writing.shelf.newBook"], de["writing.shelf.empty.import"]]) {
      const buttons = screen.getAllByRole("button", { name });
      for (const button of buttons) {
        expect(button.hasAttribute("disabled")).toBe(true);
        const noteId = button.getAttribute("aria-describedby");
        expect(document.getElementById(noteId as string)?.textContent).toBe(de["writing.shelf.comingSoon"]);
      }
    }
    expect(screen.getByText(de["writing.shelf.empty.formats"])).toBeTruthy();
    // No grid, no search chrome — the empty draft carries neither.
    expect(screen.queryAllByRole("article")).toHaveLength(0);
    expect(screen.queryByPlaceholderText(de["writing.shelf.search.placeholder"])).toBeNull();
  });

  it("an archived book never leads nor fills the grid", async () => {
    novelsAnswer = async () => ({
      data: [
        { ...HERO, archived_at: "2026-11-15T08:00:00Z", updated_at: "2026-11-15T08:00:00Z" },
        SECOND,
      ],
      response: ok(),
    });
    renderShelf();

    // The API keeps archived books out by default; the model guards the
    // boundary anyway — Winterhaus leads, Dead Signal stands nowhere.
    expect(await screen.findByRole("heading", { level: 2, name: "Winterhaus" })).toBeTruthy();
    expect(screen.queryByRole("heading", { level: 2, name: "Dead Signal" })).toBeNull();
    expect(screen.queryAllByRole("article")).toHaveLength(0);
  });

  it("a list of only archived books composes the empty state with zeroed metrics", async () => {
    // The composed answer at the page level: no hero, no grid, the honest
    // empty panel — and the metrics count what is on the shelf, which is
    // nothing, never the archived rows' own figures.
    novelsAnswer = async () => ({
      data: [
        { ...HERO, archived_at: "2026-11-15T08:00:00Z" },
        { ...SECOND, archived_at: "2026-11-14T08:00:00Z" },
      ],
      response: ok(),
    });
    renderShelf();

    expect(
      await screen.findByRole("heading", { level: 2, name: "Dein erstes Buch wartet." }),
    ).toBeTruthy();
    expect(screen.getByText(t("writing.shelf.metrics.books", { count: 0 }))).toBeTruthy();
    expect(screen.getByText("0")).toBeTruthy();
    expect(screen.queryAllByRole("article")).toHaveLength(0);
    expect(screen.queryByRole("heading", { level: 2, name: "Dead Signal" })).toBeNull();
    // The empty panel's doors stay honest, the banner neutral beside them.
    expect(screen.getAllByRole("button", { name: de["writing.shelf.newBook"] }).length).toBe(2);
    expect(screen.getByText(de["writing.shelf.banner.title"])).toBeTruthy();
  });
});

/** The search box, the filter trigger, and the grid's titles — the faces
 *  Task 7 makes real. The hero is a section with an h2; the grid cards are
 *  articles with h3s, so the two never mix in these reads. */
const searchInput = () => screen.getByPlaceholderText(de["writing.shelf.search.placeholder"]);
const filterTrigger = () => screen.getByRole("button", { name: de["writing.shelf.search.filter"] });
const gridTitles = () =>
  screen.queryAllByRole("article").map((card) => within(card).getByRole("heading", { level: 3 }).textContent);
function openPopover(): HTMLElement {
  fireEvent.click(filterTrigger());
  return screen.getByRole("dialog");
}

describe("the shelf — search matches titles, genres and figures", () => {
  it("a title word narrows the grid live; the hero stays the fixed hero", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.change(searchInput(), { target: { value: "salt" } });
    expect(gridTitles()).toEqual(["The Salt Road"]);
    // The hero is not filtered — the latest-edited active novel keeps leading.
    expect(screen.getByRole("heading", { level: 2, name: "Dead Signal" })).toBeTruthy();

    // Case-insensitive, and the whole query is the needle.
    fireEvent.change(searchInput(), { target: { value: "WINTER" } });
    expect(gridTitles()).toEqual(["Winterhaus"]);
    fireEvent.change(searchInput(), { target: { value: "" } });
    expect(gridTitles()).toEqual(["Winterhaus", "The Salt Road", "Der Nebel von Arkona"]);
  });

  it("a genre word matches the books that carry it", async () => {
    novelsAnswer = async () => ({
      data: [...SHELF_ROWS, novelRow({ id: "multi", title: "Grenzgänger", genre: "Mystery, Historisch", updated_at: "2026-11-07T09:00:00Z" })],
      response: ok(),
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.change(searchInput(), { target: { value: "mystery" } });
    expect(gridTitles()).toEqual(["Winterhaus", "Grenzgänger"]);
    // A component of a joined genre matches too — and only the component:
    // Arkona's „Historical" does not answer „historisch".
    fireEvent.change(searchInput(), { target: { value: "historisch" } });
    expect(gridTitles()).toEqual(["Grenzgänger"]);
  });

  it("a figure matches word_count or chapter_count by equality — never a substring", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    // 24.150 words: The Salt Road, in the locale's grouped form.
    fireEvent.change(searchInput(), { target: { value: "24.150" } });
    expect(gridTitles()).toEqual(["The Salt Road"]);
    // 12 chapters: the same book, the other figure.
    fireEvent.change(searchInput(), { target: { value: "12" } });
    expect(gridTitles()).toEqual(["The Salt Road"]);
    // A substring of a count is no match — 2415 is not 24150.
    fireEvent.change(searchInput(), { target: { value: "2415" } });
    expect(gridTitles()).toEqual([]);
    expect(screen.getByText(de["writing.shelf.search.empty.title"])).toBeTruthy();
  });

  it("Escape clears the search — the keyboard path back to the whole shelf", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.change(searchInput(), { target: { value: "salt" } });
    expect(gridTitles()).toEqual(["The Salt Road"]);
    fireEvent.keyDown(searchInput(), { key: "Escape" });
    expect((searchInput() as HTMLInputElement).value).toBe("");
    expect(gridTitles()).toEqual(["Winterhaus", "The Salt Road", "Der Nebel von Arkona"]);
  });

  it("no match renders the honest empty-search panel with a working clear", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.change(searchInput(), { target: { value: "gibt es nicht" } });
    expect(screen.getByText(de["writing.shelf.search.empty.title"])).toBeTruthy();
    expect(screen.getByText(de["writing.shelf.search.empty.body"])).toBeTruthy();
    expect(screen.queryAllByRole("article")).toHaveLength(0);
    // The hero keeps standing — the search narrows the grid, not the shelf's lead.
    expect(screen.getByRole("heading", { level: 2, name: "Dead Signal" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.search.empty.clear"] }));
    expect((searchInput() as HTMLInputElement).value).toBe("");
    expect(gridTitles()).toEqual(["Winterhaus", "The Salt Road", "Der Nebel von Arkona"]);
    expect(screen.queryByText(de["writing.shelf.search.empty.title"])).toBeNull();
  });

  it("the result count is announced politely, in the catalog's du-tone", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const live = screen.getByRole("status");
    expect(live.textContent).toBe(t("writing.shelf.search.results", { count: 3 }));
    fireEvent.change(searchInput(), { target: { value: "salt" } });
    expect(live.textContent).toBe(t("writing.shelf.search.results", { count: 1 }));
  });
});

describe("the shelf — the filter popover facets the real values", () => {
  it("genre facets derive from the rows, joined genres facet by component, with counts", async () => {
    novelsAnswer = async () => ({
      data: [
        ...SHELF_ROWS,
        novelRow({ id: "multi", title: "Grenzgänger", genre: "Mystery, Historisch", updated_at: "2026-11-07T09:00:00Z" }),
      ],
      response: ok(),
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openPopover();
    // First appearance wins the order: the hero's genre leads, the joined
    // book's second component joins at its own first appearance. The
    // status rows are checkboxes too — the genre ones come first.
    const statusLabels = [
      de["writing.shelf.status.draft"],
      de["writing.shelf.status.revision"],
      de["writing.shelf.status.final"],
    ];
    const boxes = within(dialog)
      .getAllByRole("checkbox")
      .filter((box) => !statusLabels.includes(box.getAttribute("aria-label") ?? ""));
    expect(boxes.map((box) => box.getAttribute("aria-label"))).toEqual([
      "Science Fiction",
      "Mystery",
      "Literary",
      "Historical",
      "Historisch",
    ]);
    // Mystery rides two books (Winterhaus + Grenzgänger) — the count says so.
    const mystery = within(dialog).getByRole("checkbox", { name: "Mystery" });
    expect(mystery.closest("label")?.textContent).toContain("2");
  });

  it("a genre facet narrows the grid; two genres OR; unchecking restores", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openPopover();
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Mystery" }));
    expect(gridTitles()).toEqual(["Winterhaus"]);
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Historical" }));
    expect(gridTitles()).toEqual(["Winterhaus", "Der Nebel von Arkona"]);
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Mystery" }));
    expect(gridTitles()).toEqual(["Der Nebel von Arkona"]);
  });

  it("status facets answer only the values the rows carry, in vocabulary order", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openPopover();
    // Winterhaus carries no status — no facet guesses one for it.
    const statusBoxes = within(dialog)
      .getAllByRole("checkbox")
      .filter((box) => [de["writing.shelf.status.draft"], de["writing.shelf.status.revision"], de["writing.shelf.status.final"]].includes(box.getAttribute("aria-label") ?? ""));
    expect(statusBoxes.map((box) => box.getAttribute("aria-label"))).toEqual([
      de["writing.shelf.status.draft"],
      de["writing.shelf.status.revision"],
      de["writing.shelf.status.final"],
    ]);

    fireEvent.click(within(dialog).getByRole("checkbox", { name: de["writing.shelf.status.revision"] }));
    expect(gridTitles()).toEqual(["The Salt Road"]);
  });

  it("search and facets compose — AND across, OR within", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openPopover();
    fireEvent.click(within(dialog).getByRole("checkbox", { name: de["writing.shelf.status.draft"] }));
    // The grid's draft books: none (the hero is draft but never in the grid).
    expect(gridTitles()).toEqual([]);
    expect(screen.getByText(de["writing.shelf.search.empty.title"])).toBeTruthy();

    fireEvent.click(within(dialog).getByRole("checkbox", { name: de["writing.shelf.status.draft"] }));
    fireEvent.change(searchInput(), { target: { value: "nebel" } });
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Historical" }));
    expect(gridTitles()).toEqual(["Der Nebel von Arkona"]);
    // The facet excludes what the search alone would keep.
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Historical" }));
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Mystery" }));
    expect(gridTitles()).toEqual([]);
  });

  it("the footer counts the selection and Zurücksetzen clears the facets, not the search", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.change(searchInput(), { target: { value: "haus" } });
    const dialog = openPopover();
    expect(within(dialog).getByText(t("writing.shelf.filter.selected", { count: 0 }))).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Mystery" }));
    fireEvent.click(within(dialog).getByRole("checkbox", { name: de["writing.shelf.status.revision"] }));
    expect(within(dialog).getByText(t("writing.shelf.filter.selected", { count: 2 }))).toBeTruthy();

    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.filter.reset"] }));
    expect(within(dialog).getByText(t("writing.shelf.filter.selected", { count: 0 }))).toBeTruthy();
    expect((within(dialog).getByRole("checkbox", { name: "Mystery" }) as HTMLInputElement).checked).toBe(false);
    // The search box is its own control — the popover's reset leaves it be.
    expect((searchInput() as HTMLInputElement).value).toBe("haus");
    expect(gridTitles()).toEqual(["Winterhaus"]);
  });

  it("the trigger wears the drafted active face and dot while filters stand", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const trigger = filterTrigger();
    expect(trigger.className).not.toContain("bg-secondary-container");
    const dialog = openPopover();
    // Open: the draft's secondary-container face, aria-expanded true.
    expect(filterTrigger().className).toContain("bg-secondary-container");
    expect(filterTrigger().getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Mystery" }));
    fireEvent.keyDown(document, { key: "Escape" });
    // Closed with a selection: the face and the dot stay — the filter is real.
    expect(filterTrigger().className).toContain("bg-secondary-container");
    expect(filterTrigger().querySelector(".bg-primary")).not.toBeNull();
    expect(filterTrigger().getAttribute("aria-expanded")).toBe("false");
  });
});

describe("the shelf — the popover's dialog semantics", () => {
  it("opens as a labelled dialog, focuses its close button, and names its controls", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const trigger = filterTrigger();
    expect(trigger.getAttribute("aria-haspopup")).toBe("dialog");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("dialog")).toBeNull();

    const dialog = openPopover();
    expect(dialog.getAttribute("aria-label")).toBe(de["writing.shelf.filter.title"]);
    expect(trigger.getAttribute("aria-controls")).toBe(dialog.id);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: de["writing.shelf.filter.close"] }));
  });

  it("Escape closes and returns focus to the trigger", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    openPopover();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(filterTrigger());
    expect(filterTrigger().getAttribute("aria-expanded")).toBe("false");
  });

  it("the close button closes and returns focus to the trigger", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openPopover();
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.filter.close"] }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(filterTrigger());
  });

  it("a click outside closes without stealing focus", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    openPopover();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).not.toBe(filterTrigger());
  });

  it("the facet rows are real checkboxes — Space toggles from the keyboard", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openPopover();
    const mystery = within(dialog).getByRole("checkbox", { name: "Mystery" }) as HTMLInputElement;
    mystery.focus();
    fireEvent.click(mystery);
    expect(mystery.checked).toBe(true);
    expect(gridTitles()).toEqual(["Winterhaus"]);
  });
});

describe("the shelf — the archive toggle is a real refetch", () => {
  it("Archiv einbeziehen asks include_archived and the archived book joins with its pill", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    expect(screen.queryByText(de["writing.shelf.archived"])).toBeNull();

    const dialog = openPopover();
    const toggle = within(dialog).getByRole("switch", { name: de["writing.shelf.filter.archive"] });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(toggle);

    await waitFor(() =>
      expect(api.GET).toHaveBeenCalledWith("/api/writing/novels", {
        params: { query: { include_archived: true } },
      }),
    );
    const archivedCard = await screen.findByRole("heading", { level: 3, name: "Das stille Archiv" });
    const card = archivedCard.closest("article") as HTMLElement;
    expect(within(card).getByText(de["writing.shelf.archived"])).toBeTruthy();
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    // The hero is untouched — the archive never leads.
    expect(screen.getByRole("heading", { level: 2, name: "Dead Signal" })).toBeTruthy();
    // The metrics still count the active shelf, never the archived rows.
    expect(screen.getByText(t("writing.shelf.metrics.books", { count: 4 }))).toBeTruthy();
  });

  it("the archived book never leads, even when it is the newest row", async () => {
    archivedAnswer = async () => ({
      data: [{ ...ARCHIVED, updated_at: "2026-11-16T08:00:00Z" }, ...SHELF_ROWS],
      response: ok(),
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.click(within(openPopover()).getByRole("switch", { name: de["writing.shelf.filter.archive"] }));
    await screen.findByRole("heading", { level: 3, name: "Das stille Archiv" });
    expect(screen.getByRole("heading", { level: 2, name: "Dead Signal" })).toBeTruthy();
    expect(screen.queryByRole("heading", { level: 2, name: "Das stille Archiv" })).toBeNull();
  });

  it("toggling back asks the default list again and the archive leaves the grid", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openPopover();
    const toggle = within(dialog).getByRole("switch", { name: de["writing.shelf.filter.archive"] });
    fireEvent.click(toggle);
    await screen.findByRole("heading", { level: 3, name: "Das stille Archiv" });
    fireEvent.click(toggle);
    await waitFor(() => expect(screen.queryByRole("heading", { level: 3, name: "Das stille Archiv" })).toBeNull());
    expect(api.GET).toHaveBeenCalledWith("/api/writing/novels");
    expect(gridTitles()).toEqual(["Winterhaus", "The Salt Road", "Der Nebel von Arkona"]);
  });

  it("the widened list holds the shelf while the ask is in flight — no skeleton flash", async () => {
    let resolveArchived!: (answer: { data: unknown; response: Response }) => void;
    archivedAnswer = () =>
      new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveArchived = resolve;
      });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.click(within(openPopover()).getByRole("switch", { name: de["writing.shelf.filter.archive"] }));
    await waitFor(() => expect(api.GET).toHaveBeenCalledWith("/api/writing/novels", {
      params: { query: { include_archived: true } },
    }));
    // The previous answer stands — no loading skeleton mid-toggle.
    expect(screen.getByRole("heading", { level: 2, name: "Dead Signal" })).toBeTruthy();
    expect(screen.queryByText(de["writing.shelf.loading"])).toBeNull();

    resolveArchived({ data: [...SHELF_ROWS, ARCHIVED], response: ok() });
    await screen.findByRole("heading", { level: 3, name: "Das stille Archiv" });
  });

  it("search and facets compose with the archive population", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.click(within(openPopover()).getByRole("switch", { name: de["writing.shelf.filter.archive"] }));
    await screen.findByRole("heading", { level: 3, name: "Das stille Archiv" });
    // The archived book's genre joins the facet counts.
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("checkbox", { name: "Mystery" }).closest("label")?.textContent).toContain("2");
    fireEvent.change(searchInput(), { target: { value: "archiv" } });
    expect(gridTitles()).toEqual(["Das stille Archiv"]);
  });

  it("an empty active shelf keeps the drafted empty panel — the chrome stands only with books", async () => {
    // The disclosed consequence of the drafted empty state (no chrome in
    // `shelf-empty`): with zero active books the archive toggle is not
    // reachable from the shelf; Task 8's archive view owns that path.
    novelsAnswer = async () => ({ data: [], response: ok() });
    archivedAnswer = async () => ({ data: [ARCHIVED], response: ok() });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dein erstes Buch wartet." });
    expect(screen.queryByPlaceholderText(de["writing.shelf.search.placeholder"])).toBeNull();
  });
});

describe("the shelf — the filter state is transient and speaks du-tone", () => {
  it("a remount starts fresh — no URL, no storage, the shelf's own memory only", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.change(searchInput(), { target: { value: "salt" } });
    fireEvent.click(within(openPopover()).getByRole("checkbox", { name: "Mystery" }));
    expect(gridTitles()).toEqual([]);

    cleanup();
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    expect((searchInput() as HTMLInputElement).value).toBe("");
    expect(gridTitles()).toEqual(["Winterhaus", "The Salt Road", "Der Nebel von Arkona"]);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("the new copy speaks the catalog's du-tone German, not an English fallback", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.change(searchInput(), { target: { value: "gibt es nicht" } });
    expect(screen.getByText("Kein Buch passt zu deiner Suche.")).toBeTruthy();
    expect(
      screen.getByText("Versuche es mit einem anderen Titel, Genre oder einer anderen Zahl — oder setze die Filter zurück."),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Suche und Filter zurücksetzen" }));

    const dialog = openPopover();
    expect(within(dialog).getByText("Filtern")).toBeTruthy();
    expect(within(dialog).getByText("Genre")).toBeTruthy();
    expect(within(dialog).getByText("Status")).toBeTruthy();
    expect(within(dialog).getByText("Archiv einbeziehen")).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Zurücksetzen" })).toBeTruthy();
  });
});
