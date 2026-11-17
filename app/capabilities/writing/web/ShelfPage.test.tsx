// @vitest-environment jsdom
/**
 * The shelf — the `shelf` draft family ported onto the shell's tokens,
 * rendered directly on a harness route under the real root route (the
 * landing's harness precedent: the settings observer, the title provider,
 * the main landmark and — since W4 Task 10 — the app-wide chrome stay
 * real). Only the API client is mocked at its module boundary; the mock
 * keeps the backend's contract — the novels list carries the rows the
 * shelf must speak, never an invented figure. The language switcher is the
 * chrome's topbar chip (the shared contract, D17 / #892); the shelf's own
 * wordmark header retired with the chrome's arrival (row 20).
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
import userEvent from "@testing-library/user-event";
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
import { formatDate } from "@shell/lib/format";
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

/** The activity aggregate as the API answers it (Task 4): thirty dense
 *  days, the last three written, today 412 — the banner's and the streak
 *  chip's real read. A test may script a failure or another day. */
const ACTIVITY_WORDS = [
  0, 0, 120, 0, 340, 0, 0, 180, 0, 0, 0, 260, 0, 0, 90, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 180, 260, 412,
];
const ACTIVITY_POINTS = ACTIVITY_WORDS.map((words, at) => ({
  date: `2026-10-${String(at + 1).padStart(2, "0")}`,
  words,
}));
function activityRow(overrides: Partial<{ points: { date: string; words: number }[]; streak_days: number; weekly_average: number; today_words: number; daily_goal_words: number | null; goal_met: boolean; goal_remaining: number }> = {}) {
  return {
    points: ACTIVITY_POINTS,
    streak_days: 3,
    weekly_average: 840,
    today_words: 412,
    daily_goal_words: null,
    goal_met: false,
    goal_remaining: 0,
    ...overrides,
  };
}
let activityAnswer: () => Promise<{ data?: unknown; response: Response }> = async () => ({
  data: activityRow(),
  response: ok(),
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
/** The quick menu's three writes (Task 8), each scriptable per test. The
 *  defaults refuse loudly so an unscripted write is a test defect, not a
 *  silent pass; a test that exercises an action scripts its answer. */
let duplicateAnswer: (novelId: string) => Promise<{ data?: unknown; response: Response }> =
  async () => {
    throw new Error("duplicate not scripted");
  };
let exportAnswer: (novelId: string) => Promise<{ data?: unknown; response: Response }> =
  async () => {
    throw new Error("export not scripted");
  };
let archiveAnswer: (
  novelId: string,
  body: { archived_at?: string | null },
) => Promise<{ data?: unknown; response: Response }> = async () => {
  throw new Error("archive not scripted");
};
/** The new-book dialog's create (Task 9), scriptable per test. The default
 *  refuses loudly so an unscripted write is a test defect, not a silent
 *  pass; a test that creates scripts its answer. */
let createAnswer: (body: {
  title?: string;
  genre?: string;
  target_words?: number;
}) => Promise<{ data?: unknown; response: Response }> = async () => {
  throw new Error("create not scripted");
};

function scriptApi() {
  api.GET.mockImplementation(async (path: string, init?: { params?: { query?: { include_archived?: boolean } } }) => {
    if (path === "/api/settings") {
      return { data: { locale: rowLocale, theme: null }, response: ok() };
    }
    if (path === "/api/writing/novels") {
      return init?.params?.query?.include_archived ? archivedAnswer() : novelsAnswer();
    }
    if (path === "/api/writing/activity") return activityAnswer();
    throw new Error(`unexpected request: ${path}`);
  });
  api.POST.mockImplementation(async (path: string, init?: { params?: { path?: { novel_id?: string } }; body?: { title?: string; genre?: string; target_words?: number } }) => {
    const novelId = init?.params?.path?.novel_id ?? "";
    if (path === "/api/writing/novels") return createAnswer(init?.body ?? {});
    if (path === "/api/writing/novels/{novel_id}/duplicate") return duplicateAnswer(novelId);
    if (path === "/api/writing/novels/{novel_id}/export") return exportAnswer(novelId);
    throw new Error(`unexpected request: ${path}`);
  });
  api.PATCH.mockImplementation(async (path: string, init?: { params?: { path?: { novel_id?: string } }; body?: { locale?: string; archived_at?: string | null } }) => {
    if (path === "/api/settings") {
      rowLocale = init?.body?.locale ?? null;
      return { data: { locale: rowLocale, theme: null }, response: ok() };
    }
    if (path === "/api/writing/novels/{novel_id}") {
      return archiveAnswer(init?.params?.path?.novel_id ?? "", init?.body ?? {});
    }
    throw new Error(`unexpected request: ${path}`);
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
  activityAnswer = async () => ({ data: activityRow(), response: ok() });
  novelsAnswer = async () => ({ data: SHELF_ROWS, response: ok() });
  archivedAnswer = async () => ({ data: [...SHELF_ROWS, ARCHIVED], response: ok() });
  duplicateAnswer = async () => {
    throw new Error("duplicate not scripted");
  };
  exportAnswer = async () => {
    throw new Error("export not scripted");
  };
  archiveAnswer = async () => {
    throw new Error("archive not scripted");
  };
  createAnswer = async () => {
    throw new Error("create not scripted");
  };
  // de-DE formatting: the word pair groups the way the reader's region does.
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  // The export's download seam: jsdom has no object URLs and a real anchor
  // click would navigate — both stand mocked so the artifact's hand-off is
  // observable (the blob, the proposed name, the one click).
  URL.createObjectURL = vi.fn(() => "blob:mock-url");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  scriptApi();
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.restoreAllMocks();
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
    // The streak is the activity aggregate's own (Task 10) — three written
    // days in a row, pluralized, never an invented day count.
    expect(screen.getByText(de["writing.shelf.metrics.streakLabel"])).toBeTruthy();
    expect(screen.getByText(t("writing.shelf.metrics.streak", { count: 3 }))).toBeTruthy();
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

  it("the top bar's new-book door opens the dialog; import stays disabled with the note", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    // Task 9 made the new-book door real: enabled, and the dialog's own face.
    const newBook = screen.getByRole("button", { name: de["writing.shelf.newBook"] });
    expect(newBook.hasAttribute("disabled")).toBe(false);
    fireEvent.click(newBook);
    expect(screen.getByRole("dialog").getAttribute("aria-modal")).toBe("true");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();

    // The import wave has not landed: its door keeps the drafted note.
    const imported = screen.getByRole("button", { name: de["writing.shelf.import"] });
    expect(imported.hasAttribute("disabled")).toBe(true);
    const noteId = imported.getAttribute("aria-describedby");
    expect(document.getElementById(noteId as string)?.textContent).toBe(de["writing.shelf.comingSoon"]);
  });

  it("the view chrome stands inert — the quick menu is live", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    // Task 7 made search and filter real; Task 8 made the quick menu real;
    // the view toggle stays honestly disabled until its own work lands.
    expect(screen.getByPlaceholderText(de["writing.shelf.search.placeholder"]).hasAttribute("disabled")).toBe(false);
    expect(screen.getByRole("button", { name: de["writing.shelf.search.filter"] }).hasAttribute("disabled")).toBe(false);
    expect(screen.getByRole("button", { name: de["writing.shelf.search.viewGrid"] }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: de["writing.shelf.search.viewList"] }).hasAttribute("disabled")).toBe(true);
    // Task 8's quick menu: one live trigger per grid card, no coming-soon note.
    const menus = screen
      .getAllByRole("article")
      .map((card) => within(card).getByRole("button", { name: de["writing.shelf.card.options"] }));
    expect(menus).toHaveLength(3);
    for (const menu of menus) {
      expect(menu.hasAttribute("disabled")).toBe(false);
      expect(menu.getAttribute("aria-haspopup")).toBe("dialog");
    }
    // #863: the hero wears the same live menu in its header row.
    const heroMenu = within(heroSection()).getByRole("button", { name: de["writing.shelf.card.options"] });
    expect(heroMenu.hasAttribute("disabled")).toBe(false);
    expect(heroMenu.getAttribute("aria-haspopup")).toBe("dialog");
    // The page-wide total guards the sum: three grid cards plus the hero —
    // a stray options trigger anywhere on the page breaks this count.
    expect(screen.getAllByRole("button", { name: de["writing.shelf.card.options"] })).toHaveLength(4);
    // Task 10 made the banner live; W4 Task 9 gave it the atelier's daily
    // goal (row 25) — unset here, the honest neutral heading stands. The
    // aggregate's weekly average; the statistics door stays disabled —
    // no statistics surface exists to open yet.
    expect(screen.getByText(de["writing.shelf.banner.noGoal"])).toBeTruthy();
    expect(screen.getByText(de["writing.shelf.banner.weekly"])).toBeTruthy();
    expect(screen.getByText("840,0 W/Tag")).toBeTruthy();
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
  // The switcher is the chrome's topbar chip now (W4 Task 10, D17 / #892):
  // the shared contract's post-setup face, the same write the shelf's
  // retired radio copy rode — the harness mounts the real shell root, so
  // the chip is live here.
  it("switching to English PATCHes the settings row and speaks English", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.click(screen.getByRole("button", { name: /Sprache/ }));
    const menu = await screen.findByRole("menu", { name: de["shell.language"] });
    fireEvent.click(within(menu).getAllByRole("menuitemradio")[1]);
    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } }),
    );
    const en = catalogs.en;
    expect(await screen.findByRole("button", { name: en["writing.shelf.hero.write"] })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Language/ }).textContent).toContain("EN (English)");
  });

  it("a refused switch restores the prior language", async () => {
    api.PATCH.mockImplementation(async () => ({
      error: { detail: "refused" },
      response: new Response(null, { status: 500 }),
    }));
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.click(screen.getByRole("button", { name: /Sprache/ }));
    const menu = await screen.findByRole("menu");
    fireEvent.click(within(menu).getAllByRole("menuitemradio")[2]);
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: de["writing.shelf.hero.write"] })).toBeTruthy(),
    );
    expect(screen.getByRole("button", { name: /Sprache/ }).textContent).toContain("DE (Deutsch)");
  });
});

describe("the shelf — loading, error and empty answer per the drafts", () => {
  it("while the list is in flight the skeleton stands — nothing invented", async () => {
    let resolveNovels!: (answer: { data: unknown; response: Response }) => void;
    novelsAnswer = () =>
      new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveNovels = resolve;
      });
    // The aggregate's ask holds too, so the streak chip's placeholder is
    // pinned deterministically — Task 10 made it wait like its siblings.
    let resolveActivity!: (answer: { data: unknown; response: Response }) => void;
    activityAnswer = () =>
      new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveActivity = resolve;
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
    // Books, words and the streak all wait as placeholders while their
    // asks are outstanding — three pulses, one strip.
    expect(strip.querySelectorAll(".animate-pulse")).toHaveLength(3);
    // No chip-height slab anywhere in the skeleton — the strip above is the only one.
    expect(status.querySelectorAll(".h-14")).toHaveLength(0);

    resolveNovels({ data: SHELF_ROWS, response: ok() });
    expect(await screen.findByRole("heading", { level: 2, name: "Dead Signal" })).toBeTruthy();
    // The skeleton's status is gone. The one status that stands with the
    // shelf now is the search's polite result announcer (Task 7).
    expect(screen.queryByText(de["writing.shelf.loading"])).toBeNull();
    expect(screen.getByRole("status").textContent).toBe(t("writing.shelf.search.results", { count: 3 }));

    resolveActivity({ data: activityRow(), response: ok() });
    expect(await screen.findByText(t("writing.shelf.metrics.streak", { count: 3 }))).toBeTruthy();
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

  it("an empty shelf opens the honest empty state — the new-book door live", async () => {
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

    // The empty panel's new-book door is real (Task 9) — both copies of it
    // open the dialog; the import door keeps the drafted note.
    const doors = screen.getAllByRole("button", { name: de["writing.shelf.newBook"] });
    expect(doors).toHaveLength(2);
    for (const door of doors) expect(door.hasAttribute("disabled")).toBe(false);
    fireEvent.click(doors[1]);
    expect(screen.getByRole("dialog").getAttribute("aria-modal")).toBe("true");
    fireEvent.keyDown(document, { key: "Escape" });
    const imported = screen.getByRole("button", { name: de["writing.shelf.empty.import"] });
    expect(imported.hasAttribute("disabled")).toBe(true);
    const noteId = imported.getAttribute("aria-describedby");
    expect(document.getElementById(noteId as string)?.textContent).toBe(de["writing.shelf.comingSoon"]);
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
    // The empty panel's doors stay honest; the banner names no goal beside
    // them — none is stored (the aggregate still speaks).
    expect(screen.getAllByRole("button", { name: de["writing.shelf.newBook"] }).length).toBe(2);
    expect(screen.getByText(de["writing.shelf.banner.noGoal"])).toBeTruthy();
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
    const user = userEvent.setup();
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openPopover();
    const mystery = within(dialog).getByRole("checkbox", { name: "Mystery" }) as HTMLInputElement;
    mystery.focus();
    // Real key events, not a click in disguise: Space checks and unchecks.
    await user.keyboard(" ");
    expect(mystery.checked).toBe(true);
    expect(gridTitles()).toEqual(["Winterhaus"]);
    await user.keyboard(" ");
    expect(mystery.checked).toBe(false);
    expect(gridTitles()).toEqual(["Winterhaus", "The Salt Road", "Der Nebel von Arkona"]);
  });

  it("Escape is staged — the box's text first, the panel second", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    fireEvent.change(searchInput(), { target: { value: "salt" } });
    openPopover();
    // Focus back in the box with the panel standing: the first Escape
    // clears the query and stops there — panel open, focus in the box.
    searchInput().focus();
    fireEvent.keyDown(searchInput(), { key: "Escape" });
    expect((searchInput() as HTMLInputElement).value).toBe("");
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(document.activeElement).toBe(searchInput());
    // The second Escape, the box now empty, closes the panel and returns
    // focus to the trigger — the innermost context had its turn first.
    fireEvent.keyDown(searchInput(), { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(filterTrigger());
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
    const pill = within(card).getByText(de["writing.shelf.archived"]);
    expect(pill).toBeTruthy();
    // The review's contrast fix pinned: the revision pill's own passing
    // pair on this surface, never the muted ink that failed AA.
    expect(pill.className).toContain("bg-surface-container-high");
    expect(pill.className).toContain("text-secondary");
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

/** The quick menu (Task 8) — the per-card Schnellauswahl, real. The trigger
 *  lives in the card's top-right; the menu and its confirm are non-modal
 *  dialogs on the filter popover's discipline. The grid cards are articles
 *  with h3s, so a card's own trigger and notices read through `within`. */
const menuTriggerOf = (title: string) =>
  within(cardOf(title)).getByRole("button", { name: de["writing.shelf.card.options"] });
function openMenu(title: string): HTMLElement {
  fireEvent.click(menuTriggerOf(title));
  return screen.getByRole("dialog");
}
/** The meta line's date face — the draft's „14. Feb. 2026" grammar. */
const DATE_OPTS = { day: "numeric", month: "short", year: "numeric" } as const;
const COPY = novelRow({
  id: "99999999-9999-9999-9999-999999999999",
  title: "Winterhaus (Kopie)",
  genre: "Mystery",
  // Older than the hero so the copy joins the grid (a fresh server copy
  // would lead as hero — the live look shows that; here the grid refetch
  // is the pin).
  updated_at: "2026-11-13T12:00:00Z",
});

describe("the shelf — the quick menu opens with the draft's dialog discipline", () => {
  it("the trigger opens a labelled menu and focuses its first action", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const trigger = menuTriggerOf("Winterhaus");
    expect(trigger.getAttribute("aria-haspopup")).toBe("dialog");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("dialog")).toBeNull();

    const dialog = openMenu("Winterhaus");
    expect(dialog.getAttribute("aria-label")).toBe(de["writing.shelf.menu.title"]);
    expect(trigger.getAttribute("aria-controls")).toBe(dialog.id);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    // The draft's three actions, in order, and the honest export meta.
    for (const name of [
      de["writing.shelf.menu.duplicate"],
      de["writing.shelf.menu.export"],
      de["writing.shelf.menu.archive"],
    ]) {
      expect(within(dialog).getByRole("button", { name })).toBeTruthy();
    }
    expect(within(dialog).getByText(de["writing.shelf.menu.lastExport"])).toBeTruthy();
    // Opening moves focus to the first action — the popover discipline.
    expect(document.activeElement).toBe(
      within(dialog).getByRole("button", { name: de["writing.shelf.menu.duplicate"] }),
    );
  });

  it("Escape closes the menu and returns focus to the trigger", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    openMenu("Winterhaus");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(menuTriggerOf("Winterhaus"));
    expect(menuTriggerOf("Winterhaus").getAttribute("aria-expanded")).toBe("false");
  });

  it("an outside press closes without stealing focus", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    openMenu("Winterhaus");
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).not.toBe(menuTriggerOf("Winterhaus"));
  });

  it("the trigger wears the draft's open face while the menu stands", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const trigger = menuTriggerOf("Winterhaus");
    expect(trigger.className).toContain("border-border");
    expect(trigger.className).not.toContain("border-primary");
    openMenu("Winterhaus");
    expect(menuTriggerOf("Winterhaus").className).toContain("border-primary");
  });
});

describe("the shelf — the menu's meta line answers the row's own truth", () => {
  it("a never-exported book shows the honest dash", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openMenu("Winterhaus");
    expect(within(dialog).getByText(de["writing.shelf.menu.lastExport"])).toBeTruthy();
    expect(within(dialog).getByText("—")).toBeTruthy();
  });

  it("an exported book shows the localized date", async () => {
    novelsAnswer = async () => ({
      data: [HERO, { ...SECOND, last_exported_at: "2026-02-14T10:00:00Z" }, THIRD, FOURTH],
      response: ok(),
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openMenu("Winterhaus");
    expect(
      within(dialog).getByText(formatDate("2026-02-14T10:00:00Z", DATE_OPTS)),
    ).toBeTruthy();
  });

  it("the archived menu shows the archive date in the archive's own header", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    fireEvent.click(within(openPopover()).getByRole("switch", { name: de["writing.shelf.filter.archive"] }));
    await screen.findByRole("heading", { level: 3, name: "Das stille Archiv" });
    fireEvent.keyDown(document, { key: "Escape" }); // close the filter popover

    const dialog = openMenu("Das stille Archiv");
    expect(dialog.getAttribute("aria-label")).toBe(de["writing.shelf.menu.titleArchived"]);
    expect(within(dialog).getByText(de["writing.shelf.menu.archivedAt"])).toBeTruthy();
    expect(
      within(dialog).getByText(formatDate(ARCHIVED.archived_at as string, DATE_OPTS)),
    ).toBeTruthy();
  });
});

describe("the shelf — duplicate acts for real", () => {
  it("duplicate runs busy, then the copy joins the shelf with its own figures", async () => {
    let resolveDup!: (answer: { data: unknown; response: Response }) => void;
    duplicateAnswer = () =>
      new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveDup = resolve;
      });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    novelsAnswer = async () => ({ data: [...SHELF_ROWS, COPY], response: ok() });

    const dialog = openMenu("Winterhaus");
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.duplicate"] }));
    // Busy: the acting row spins, the menu stays open, the rest wait.
    expect(within(dialog).getByText(de["writing.shelf.menu.wait"])).toBeTruthy();
    expect(dialog.querySelector(".animate-spin")).not.toBeNull();
    expect(
      within(dialog).getByRole("button", { name: new RegExp(de["writing.shelf.menu.duplicate"]) }).hasAttribute("disabled"),
    ).toBe(true);
    expect(
      within(dialog).getByRole("button", { name: de["writing.shelf.menu.export"] }).hasAttribute("disabled"),
    ).toBe(true);

    // The mutation's ask runs in a microtask — yield until it lands so the
    // controlled promise's resolve handle is assigned.
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    resolveDup({ data: COPY, response: ok() });
    expect(await screen.findByRole("heading", { level: 3, name: "Winterhaus (Kopie)" })).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.POST).toHaveBeenCalledWith("/api/writing/novels/{novel_id}/duplicate", {
      params: { path: { novel_id: SECOND.id } },
    });
  });

  it("a refused duplicate closes the menu and names the loss-free error with a working retry", async () => {
    let attempts = 0;
    duplicateAnswer = async () => {
      attempts += 1;
      if (attempts === 1) return { data: undefined, response: new Response(null, { status: 500 }) };
      return { data: COPY, response: ok() };
    };
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    novelsAnswer = async () => ({ data: [...SHELF_ROWS, COPY], response: ok() });

    const dialog = openMenu("Winterhaus");
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.duplicate"] }));

    const card = cardOf("Winterhaus");
    const alert = await within(card).findByRole("alert");
    expect(alert.textContent).toContain(de["writing.shelf.menu.error.duplicate"]);
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(within(alert).getByRole("button", { name: de["writing.shelf.error.retry"] }));
    expect(await screen.findByRole("heading", { level: 3, name: "Winterhaus (Kopie)" })).toBeTruthy();
    expect(within(cardOf("Winterhaus")).queryByRole("alert")).toBeNull();
    expect(attempts).toBe(2);
  });
});

describe("the shelf — export lands the artifact and refreshes the meta line", () => {
  it("export downloads the ZIP the server names and keeps the menu open on the fresh date", async () => {
    const blob = new Blob(["zip-bytes"], { type: "application/zip" });
    exportAnswer = async () => ({
      data: blob,
      response: new Response(null, {
        status: 200,
        headers: { "Content-Disposition": 'attachment; filename="winterhaus.zip"' },
      }),
    });
    let downloadedName = "";
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      downloadedName = this.download;
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    novelsAnswer = async () => ({
      data: [HERO, { ...SECOND, last_exported_at: "2026-11-15T12:00:00Z" }, THIRD, FOURTH],
      response: ok(),
    });

    const dialog = openMenu("Winterhaus");
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.export"] }));
    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalledWith(blob));
    expect(downloadedName).toBe("winterhaus.zip");
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalled();
    // The menu stays open and the meta line refetches to the new date.
    expect(screen.getByRole("dialog")).toBeTruthy();
    await waitFor(() =>
      expect(within(screen.getByRole("dialog")).getByText(formatDate("2026-11-15T12:00:00Z", DATE_OPTS))).toBeTruthy(),
    );
    expect(api.POST).toHaveBeenCalledWith("/api/writing/novels/{novel_id}/export", {
      params: { path: { novel_id: SECOND.id } },
      body: { mode: "zip" },
      parseAs: "blob",
    });
  });

  it("a refused export names the loss-free error with a retry", async () => {
    exportAnswer = async () => ({ data: undefined, response: new Response(null, { status: 500 }) });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openMenu("Winterhaus");
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.export"] }));
    const alert = await within(cardOf("Winterhaus")).findByRole("alert");
    expect(alert.textContent).toContain(de["writing.shelf.menu.error.export"]);
    expect(within(alert).getByRole("button", { name: de["writing.shelf.error.retry"] })).toBeTruthy();
  });
});

describe("the shelf — archive confirms in the draft's own words, then moves the card", () => {
  it("Archivieren opens the drafted confirm with the book's own name — no alarm red", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openMenu("Winterhaus");
    const archiveRow = within(dialog).getByRole("button", { name: de["writing.shelf.menu.archive"] });
    expect(archiveRow.className).not.toContain("text-danger");
    fireEvent.click(archiveRow);

    const confirm = screen.getByRole("dialog");
    expect(within(confirm).getByText(de["writing.shelf.menu.confirm.title"])).toBeTruthy();
    expect(
      within(confirm).getByText(t("writing.shelf.menu.confirm.body", { title: "Winterhaus" })),
    ).toBeTruthy();
    expect(within(confirm).getByRole("button", { name: de["writing.shelf.menu.confirm.cancel"] })).toBeTruthy();
    const action = within(confirm).getByRole("button", { name: de["writing.shelf.menu.archive"] });
    expect(action.className).not.toContain("text-danger");
    expect(document.activeElement).toBe(action);
  });

  it("Abbrechen returns to the menu without archiving", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openMenu("Winterhaus");
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.archive"] }));
    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.menu.confirm.cancel"] }));
    expect(screen.getByRole("dialog").getAttribute("aria-label")).toBe(de["writing.shelf.menu.title"]);
    expect(api.PATCH).not.toHaveBeenCalledWith("/api/writing/novels/{novel_id}", expect.anything());
  });

  it("confirming archives — the PATCH carries a timestamp and the card leaves the default grid", async () => {
    archiveAnswer = async (_id, body) => ({
      data: { ...SECOND, archived_at: body.archived_at },
      response: ok(),
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    novelsAnswer = async () => ({ data: [HERO, THIRD, FOURTH], response: ok() });

    const dialog = openMenu("Winterhaus");
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.archive"] }));
    const confirm = screen.getByRole("dialog");
    fireEvent.click(within(confirm).getByRole("button", { name: de["writing.shelf.menu.archive"] }));
    // Busy on the confirm action while the ask is outstanding.
    expect(confirm.querySelector(".animate-spin")).not.toBeNull();

    await waitFor(() => expect(screen.queryByRole("heading", { level: 3, name: "Winterhaus" })).toBeNull());
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.PATCH).toHaveBeenCalledWith("/api/writing/novels/{novel_id}", {
      params: { path: { novel_id: SECOND.id } },
      body: { archived_at: expect.any(String) },
    });
  });

  it("a refused archive names the loss-free error with a retry", async () => {
    archiveAnswer = async () => ({ data: undefined, response: new Response(null, { status: 500 }) });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openMenu("Winterhaus");
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.archive"] }));
    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.menu.archive"] }));
    const alert = await within(cardOf("Winterhaus")).findByRole("alert");
    expect(alert.textContent).toContain(de["writing.shelf.menu.error.archive"]);
    expect(within(alert).getByRole("button", { name: de["writing.shelf.error.retry"] })).toBeTruthy();
  });

  it("Escape is staged — the confirm first, then the menu", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openMenu("Winterhaus");
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.archive"] }));
    // First Escape: the confirm yields to the menu, focus on the archive row.
    fireEvent.keyDown(document, { key: "Escape" });
    const menu = screen.getByRole("dialog");
    expect(menu.getAttribute("aria-label")).toBe(de["writing.shelf.menu.title"]);
    expect(document.activeElement).toBe(
      within(menu).getByRole("button", { name: de["writing.shelf.menu.archive"] }),
    );
    // Second Escape: the menu closes, focus back to the trigger.
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(menuTriggerOf("Winterhaus"));
  });
});

describe("the shelf — the archived book restores without a confirm", () => {
  it("the archived menu offers Wiederherstellen and restores on one click", async () => {
    archiveAnswer = async (_id, body) => ({
      data: { ...ARCHIVED, archived_at: body.archived_at },
      response: ok(),
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    fireEvent.click(within(openPopover()).getByRole("switch", { name: de["writing.shelf.filter.archive"] }));
    await screen.findByRole("heading", { level: 3, name: "Das stille Archiv" });
    fireEvent.keyDown(document, { key: "Escape" });
    archivedAnswer = async () => ({
      data: [...SHELF_ROWS, { ...ARCHIVED, archived_at: null }],
      response: ok(),
    });

    const dialog = openMenu("Das stille Archiv");
    expect(within(dialog).getByRole("button", { name: de["writing.shelf.menu.restore"] })).toBeTruthy();
    expect(within(dialog).queryByRole("button", { name: de["writing.shelf.menu.archive"] })).toBeNull();
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.restore"] }));
    // No confirm — the draft's symmetric return is immediate.
    expect(screen.queryByText(de["writing.shelf.menu.confirm.title"])).toBeNull();

    const card = cardOf("Das stille Archiv");
    await waitFor(() => expect(within(card).queryByText(de["writing.shelf.archived"])).toBeNull());
    expect(api.PATCH).toHaveBeenCalledWith("/api/writing/novels/{novel_id}", {
      params: { path: { novel_id: ARCHIVED.id } },
      body: { archived_at: null },
    });
    // The restored book's menu now offers the forward action again.
    const reopened = openMenu("Das stille Archiv");
    expect(within(reopened).getByRole("button", { name: de["writing.shelf.menu.archive"] })).toBeTruthy();
  });

  it("a refused restore names the loss-free error", async () => {
    archiveAnswer = async () => ({ data: undefined, response: new Response(null, { status: 500 }) });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    fireEvent.click(within(openPopover()).getByRole("switch", { name: de["writing.shelf.filter.archive"] }));
    await screen.findByRole("heading", { level: 3, name: "Das stille Archiv" });
    fireEvent.keyDown(document, { key: "Escape" });

    const dialog = openMenu("Das stille Archiv");
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.restore"] }));
    const alert = await within(cardOf("Das stille Archiv")).findByRole("alert");
    expect(alert.textContent).toContain(de["writing.shelf.menu.error.restore"]);
  });
});

describe("the shelf — the empty shelf's archive door closes Task 7's gap", () => {
  it("the empty shelf offers a live archive door that opens the archive-included list", async () => {
    novelsAnswer = async () => ({ data: [], response: ok() });
    archivedAnswer = async () => ({ data: [ARCHIVED], response: ok() });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dein erstes Buch wartet." });

    const door = screen.getByRole("button", { name: de["writing.shelf.empty.archiveDoor"] });
    expect(door.hasAttribute("disabled")).toBe(false);
    fireEvent.click(door);
    await waitFor(() =>
      expect(api.GET).toHaveBeenCalledWith("/api/writing/novels", {
        params: { query: { include_archived: true } },
      }),
    );
    expect(await screen.findByRole("heading", { level: 3, name: "Das stille Archiv" })).toBeTruthy();
  });

  it("an empty archive answers the draft's honest line, not a dead door", async () => {
    novelsAnswer = async () => ({ data: [], response: ok() });
    archivedAnswer = async () => ({ data: [], response: ok() });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dein erstes Buch wartet." });

    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.empty.archiveDoor"] }));
    expect(await screen.findByText(de["writing.shelf.empty.archiveEmpty"])).toBeTruthy();
    expect(screen.queryByRole("button", { name: de["writing.shelf.empty.archiveDoor"] })).toBeNull();
  });
});

describe("the shelf — the quick menu's review fixes", () => {
  it("the popover's container chain never clips it — no overflow clip up to the page", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openMenu("Winterhaus");
    // The lg-band columns run 222–264px while the popover needs 264px; the
    // draft lets it overhang freely. Walk the ancestor chain: no element
    // between the popover and the content region may carry an overflow
    // clip, or the narrow card would sever the menu's icons and first
    // characters. Since the app-wide chrome (W4 Task 10) the content's
    // scroll region is the shell's `main` — the popover's page — and the
    // walk ends there; the chrome's own frame above it is the shell's.
    const clippers: string[] = [];
    let node: HTMLElement | null = dialog;
    while (node && node !== document.body) {
      if (/overflow-(hidden|clip|x-hidden|y-hidden|x-clip|y-clip)/.test(node.className)) {
        clippers.push(`${node.tagName}.${node.className}`);
      }
      if (node.id === "main") break;
      node = node.parentElement;
    }
    expect(clippers).toEqual([]);
    // The cover geometry is preserved by the pedestal itself: it rounds its
    // own top corners and keeps its own clip (the cover's hover lift), while
    // the article carries none.
    const article = cardOf("Winterhaus");
    expect(article.className).not.toMatch(/overflow-(hidden|clip)/);
    const pedestal = article.firstElementChild as HTMLElement;
    expect(pedestal.className).toContain("rounded-t-xl");
    expect(pedestal.className).toContain("overflow-hidden");
  });

  it("the trigger holds the menu open while an action is busy", async () => {
    let resolveExport!: (answer: { data: unknown; response: Response }) => void;
    exportAnswer = () =>
      new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveExport = resolve;
      });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openMenu("Winterhaus");
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.export"] }));
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    expect(screen.getByRole("dialog")).toBeTruthy();

    // Clicking the trigger mid-flight must not close the menu — the busy
    // guard matches Escape and the outside press.
    fireEvent.click(menuTriggerOf("Winterhaus"));
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(menuTriggerOf("Winterhaus").getAttribute("aria-expanded")).toBe("true");

    resolveExport({
      data: new Blob(["zip"], { type: "application/zip" }),
      response: new Response(null, { status: 200, headers: { "Content-Disposition": 'attachment; filename="w.zip"' } }),
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeTruthy());
  });

  it("opening the menu dismisses a standing error notice for good", async () => {
    duplicateAnswer = async () => ({ data: undefined, response: new Response(null, { status: 500 }) });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openMenu("Winterhaus");
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.duplicate"] }));
    await within(cardOf("Winterhaus")).findByRole("alert");

    // Engaging the menu clears the notice…
    fireEvent.click(menuTriggerOf("Winterhaus"));
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(within(cardOf("Winterhaus")).queryByRole("alert")).toBeNull();
    // …so closing without acting never brings it back stale.
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(within(cardOf("Winterhaus")).queryByRole("alert")).toBeNull();
  });

  it("export restores focus to its row once busy clears — no keyboard strand", async () => {
    let resolveExport!: (answer: { data: unknown; response: Response }) => void;
    exportAnswer = () =>
      new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveExport = resolve;
      });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openMenu("Winterhaus");
    const exportRow = within(dialog).getByRole("button", { name: de["writing.shelf.menu.export"] });
    fireEvent.click(exportRow);
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    // The row is disabled while busy; the browser drops a disabled row's
    // focus to the body. jsdom neither auto-blurs nor blurs a disabled
    // element, so strand focus on the body explicitly (via an enabled
    // control) to reproduce the keyboard trap the fix repairs.
    menuTriggerOf("Winterhaus").focus();
    (document.activeElement as HTMLElement).blur();
    expect(document.activeElement).toBe(document.body);

    resolveExport({
      data: new Blob(["zip"], { type: "application/zip" }),
      response: new Response(null, { status: 200, headers: { "Content-Disposition": 'attachment; filename="w.zip"' } }),
    });
    // The menu stays open and focus lands back on the live export row.
    await waitFor(() => expect(document.activeElement).toBe(exportRow));
    expect(screen.getByRole("dialog")).toBeTruthy();
  });
});

/** The hero's quick menu (#863) — the grid's same surface, anchored in the
 *  hero's header row (the `shelf-hero-menu` draft). The hero never shows an
 *  archived book (pickHero), so the menu always offers the three forward
 *  actions; archiving the hero re-picks the next active book through the
 *  same `["novels"]` refetch — no special case, no empty hero gap. */
const heroTrigger = () =>
  within(heroSection()).getByRole("button", { name: de["writing.shelf.card.options"] });
function openHeroMenu(): HTMLElement {
  fireEvent.click(heroTrigger());
  return screen.getByRole("dialog");
}

describe("the shelf — the hero book acts through the same quick menu", () => {
  it("the hero's trigger opens the same labelled menu — three actions, no restore", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const trigger = heroTrigger();
    expect(trigger.getAttribute("aria-haspopup")).toBe("dialog");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("dialog")).toBeNull();

    const dialog = openHeroMenu();
    expect(dialog.getAttribute("aria-label")).toBe(de["writing.shelf.menu.title"]);
    expect(trigger.getAttribute("aria-controls")).toBe(dialog.id);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    for (const name of [
      de["writing.shelf.menu.duplicate"],
      de["writing.shelf.menu.export"],
      de["writing.shelf.menu.archive"],
    ]) {
      expect(within(dialog).getByRole("button", { name })).toBeTruthy();
    }
    // The hero is never archived — the restore variant has no place here.
    expect(within(dialog).queryByRole("button", { name: de["writing.shelf.menu.restore"] })).toBeNull();
    // The honest meta line: Dead Signal was never exported.
    expect(within(dialog).getByText(de["writing.shelf.menu.lastExport"])).toBeTruthy();
    expect(within(dialog).getByText("—")).toBeTruthy();
    // Opening moves focus to the first action — the popover discipline.
    expect(document.activeElement).toBe(
      within(dialog).getByRole("button", { name: de["writing.shelf.menu.duplicate"] }),
    );
  });

  it("the hero trigger wears the draft's two faces", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    expect(heroTrigger().className).toContain("border-border");
    expect(heroTrigger().className).not.toContain("border-primary");
    openHeroMenu();
    expect(heroTrigger().className).toContain("border-primary");
  });

  it("Escape closes the hero menu and returns focus to its trigger", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    openHeroMenu();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(heroTrigger());
    expect(heroTrigger().getAttribute("aria-expanded")).toBe("false");
  });

  it("an outside press closes the hero menu without stealing focus", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    openHeroMenu();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).not.toBe(heroTrigger());
  });

  it("duplicate from the hero runs busy, then the copy joins the grid", async () => {
    let resolveDup!: (answer: { data: unknown; response: Response }) => void;
    duplicateAnswer = () =>
      new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveDup = resolve;
      });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    novelsAnswer = async () => ({ data: [...SHELF_ROWS, COPY], response: ok() });

    const dialog = openHeroMenu();
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.duplicate"] }));
    expect(within(dialog).getByText(de["writing.shelf.menu.wait"])).toBeTruthy();
    expect(dialog.querySelector(".animate-spin")).not.toBeNull();
    expect(
      within(dialog).getByRole("button", { name: de["writing.shelf.menu.export"] }).hasAttribute("disabled"),
    ).toBe(true);

    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    resolveDup({ data: COPY, response: ok() });
    expect(await screen.findByRole("heading", { level: 3, name: "Winterhaus (Kopie)" })).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.POST).toHaveBeenCalledWith("/api/writing/novels/{novel_id}/duplicate", {
      params: { path: { novel_id: HERO.id } },
    });
  });

  it("export from the hero downloads the ZIP and keeps the menu open on the fresh date", async () => {
    const blob = new Blob(["zip-bytes"], { type: "application/zip" });
    exportAnswer = async () => ({
      data: blob,
      response: new Response(null, {
        status: 200,
        headers: { "Content-Disposition": 'attachment; filename="dead-signal.zip"' },
      }),
    });
    let downloadedName = "";
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      downloadedName = this.download;
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    novelsAnswer = async () => ({
      data: [{ ...HERO, last_exported_at: "2026-11-15T12:00:00Z" }, SECOND, THIRD, FOURTH],
      response: ok(),
    });

    const dialog = openHeroMenu();
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.export"] }));
    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalledWith(blob));
    expect(downloadedName).toBe("dead-signal.zip");
    expect(screen.getByRole("dialog")).toBeTruthy();
    await waitFor(() =>
      expect(within(screen.getByRole("dialog")).getByText(formatDate("2026-11-15T12:00:00Z", DATE_OPTS))).toBeTruthy(),
    );
    expect(api.POST).toHaveBeenCalledWith("/api/writing/novels/{novel_id}/export", {
      params: { path: { novel_id: HERO.id } },
      body: { mode: "zip" },
      parseAs: "blob",
    });
  });

  it("Archivieren opens the drafted confirm with the hero's own name; Abbrechen returns", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openHeroMenu();
    const archiveRow = within(dialog).getByRole("button", { name: de["writing.shelf.menu.archive"] });
    expect(archiveRow.className).not.toContain("text-danger");
    fireEvent.click(archiveRow);

    const confirm = screen.getByRole("dialog");
    expect(within(confirm).getByText(de["writing.shelf.menu.confirm.title"])).toBeTruthy();
    expect(
      within(confirm).getByText(t("writing.shelf.menu.confirm.body", { title: "Dead Signal" })),
    ).toBeTruthy();
    const action = within(confirm).getByRole("button", { name: de["writing.shelf.menu.archive"] });
    expect(action.className).not.toContain("text-danger");
    expect(document.activeElement).toBe(action);

    fireEvent.click(within(confirm).getByRole("button", { name: de["writing.shelf.menu.confirm.cancel"] }));
    expect(screen.getByRole("dialog").getAttribute("aria-label")).toBe(de["writing.shelf.menu.title"]);
    expect(api.PATCH).not.toHaveBeenCalledWith("/api/writing/novels/{novel_id}", expect.anything());
  });

  it("confirming archives the hero — the next active book leads, no empty gap", async () => {
    archiveAnswer = async (_id, body) => ({
      data: { ...HERO, archived_at: body.archived_at },
      response: ok(),
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    novelsAnswer = async () => ({ data: [SECOND, THIRD, FOURTH], response: ok() });

    const dialog = openHeroMenu();
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.archive"] }));
    const confirm = screen.getByRole("dialog");
    fireEvent.click(within(confirm).getByRole("button", { name: de["writing.shelf.menu.archive"] }));
    expect(confirm.querySelector(".animate-spin")).not.toBeNull();

    // The honest re-pick: Winterhaus leads as the hero, Dead Signal stands
    // nowhere, the grid holds the rest — no special case, the same refetch.
    expect(await screen.findByRole("heading", { level: 2, name: "Winterhaus" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Dead Signal" })).toBeNull();
    const titles = screen
      .getAllByRole("article")
      .map((card) => within(card).getByRole("heading", { level: 3 }).textContent);
    expect(titles).toEqual(["The Salt Road", "Der Nebel von Arkona"]);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByText(t("writing.shelf.metrics.books", { count: 3 }))).toBeTruthy();
    expect(api.PATCH).toHaveBeenCalledWith("/api/writing/novels/{novel_id}", {
      params: { path: { novel_id: HERO.id } },
      body: { archived_at: expect.any(String) },
    });
  });

  it("archiving the shelf's last active book answers the honest empty state", async () => {
    archiveAnswer = async (_id, body) => ({
      data: { ...HERO, archived_at: body.archived_at },
      response: ok(),
    });
    novelsAnswer = async () => ({ data: [HERO], response: ok() });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    novelsAnswer = async () => ({ data: [], response: ok() });

    const dialog = openHeroMenu();
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.archive"] }));
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: de["writing.shelf.menu.archive"] }),
    );

    expect(await screen.findByRole("heading", { level: 2, name: "Dein erstes Buch wartet." })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Dead Signal" })).toBeNull();
    expect(screen.queryAllByRole("article")).toHaveLength(0);
  });

  it("a refused archive leaves the hero's error line; the retry re-runs and the next book leads", async () => {
    let attempts = 0;
    archiveAnswer = async (_id, body) => {
      attempts += 1;
      if (attempts === 1) return { data: undefined, response: new Response(null, { status: 500 }) };
      novelsAnswer = async () => ({ data: [SECOND, THIRD, FOURTH], response: ok() });
      return { data: { ...HERO, archived_at: body.archived_at }, response: ok() };
    };
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openHeroMenu();
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.archive"] }));
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: de["writing.shelf.menu.archive"] }),
    );

    const alert = await within(heroSection()).findByRole("alert");
    expect(alert.textContent).toContain(de["writing.shelf.menu.error.archive"]);
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(within(alert).getByRole("button", { name: de["writing.shelf.error.retry"] }));
    expect(await screen.findByRole("heading", { level: 2, name: "Winterhaus" })).toBeTruthy();
    expect(attempts).toBe(2);
  });

  it("a refused duplicate leaves the hero's error line; opening the menu dismisses it for good", async () => {
    duplicateAnswer = async () => ({ data: undefined, response: new Response(null, { status: 500 }) });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openHeroMenu();
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.duplicate"] }));
    await within(heroSection()).findByRole("alert");

    fireEvent.click(heroTrigger());
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(within(heroSection()).queryByRole("alert")).toBeNull();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(within(heroSection()).queryByRole("alert")).toBeNull();
  });

  it("Escape is staged on the hero — the confirm first, then the menu", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openHeroMenu();
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.archive"] }));
    fireEvent.keyDown(document, { key: "Escape" });
    const menu = screen.getByRole("dialog");
    expect(menu.getAttribute("aria-label")).toBe(de["writing.shelf.menu.title"]);
    expect(document.activeElement).toBe(
      within(menu).getByRole("button", { name: de["writing.shelf.menu.archive"] }),
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(heroTrigger());
  });

  it("the trigger holds the hero menu open while an action is busy", async () => {
    let resolveExport!: (answer: { data: unknown; response: Response }) => void;
    exportAnswer = () =>
      new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveExport = resolve;
      });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openHeroMenu();
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.export"] }));
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    expect(screen.getByRole("dialog")).toBeTruthy();

    fireEvent.click(heroTrigger());
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(heroTrigger().getAttribute("aria-expanded")).toBe("true");

    resolveExport({
      data: new Blob(["zip"], { type: "application/zip" }),
      response: new Response(null, { status: 200, headers: { "Content-Disposition": 'attachment; filename="d.zip"' } }),
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeTruthy());
  });

  it("the hero popover's container chain never clips it — the section carries no overflow clip", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openHeroMenu();
    // The draft lets the popover overhang the hero's edge freely; walk the
    // ancestor chain: no element between the popover and the content
    // region (the shell's `main` since the app-wide chrome, W4 Task 10)
    // may clip.
    const clippers: string[] = [];
    let node: HTMLElement | null = dialog;
    while (node && node !== document.body) {
      if (/overflow-(hidden|clip|x-hidden|y-hidden|x-clip|y-clip)/.test(node.className)) {
        clippers.push(`${node.tagName}.${node.className}`);
      }
      if (node.id === "main") break;
      node = node.parentElement;
    }
    expect(clippers).toEqual([]);
    expect(heroSection().className).not.toMatch(/overflow-(hidden|clip)/);
  });
});

/** The new-book dialog (Task 9) — the picked draft's modal over the scrimmed
 *  shelf. Opened from either door; the create is the real POST seam, the
 *  shelf's refetch the honest insert (the hook invalidates `["novels"]`). */
const topNewBook = () => screen.getAllByRole("button", { name: de["writing.shelf.newBook"] })[0];
function openNewBook(from: HTMLElement = topNewBook()): HTMLElement {
  fireEvent.click(from);
  return screen.getByRole("dialog");
}
const titleField = (dialog: HTMLElement) => within(dialog).getByRole("textbox");
const createButton = (dialog: HTMLElement) =>
  within(dialog).getByRole("button", { name: de["writing.shelf.dialog.create"] });
const coverOf = (dialog: HTMLElement) => dialog.querySelector("[data-channel]") as HTMLElement;

/** The row the create answers — newest updated_at, so the shelf's honest
 *  outcome is the hero, never a hand-patched grid insert. */
const CREATED = novelRow({
  id: "99999999-9999-9999-9999-999999999999",
  title: "Die Winterchronik von Station Sieben",
  genre: "Science Fiction & Speculative, Mystery & Noir",
  target_words: 80000,
  created_at: "2026-11-15T12:00:00Z",
  updated_at: "2026-11-15T12:00:00Z",
});
/** A create that lands: the server's list grows, the refetch carries it. */
function scriptCreate() {
  createAnswer = async (body) => {
    novelsAnswer = async () => ({ data: [CREATED, ...SHELF_ROWS], response: ok() });
    return {
      data: { ...CREATED, title: body.title ?? CREATED.title, genre: body.genre ?? null, target_words: body.target_words ?? null },
      response: new Response(null, { status: 201 }),
    };
  };
}

describe("the shelf — the new-book dialog is the drafted modal", () => {
  it("opens over the 40% scrim with the draft's three fields and the verbatim note", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openNewBook();
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    const labelledBy = dialog.getAttribute("aria-labelledby");
    expect(document.getElementById(labelledBy as string)?.textContent).toBe(de["writing.shelf.dialog.title"]);
    expect(within(dialog).getByRole("heading", { level: 2, name: de["writing.shelf.dialog.title"] })).toBeTruthy();
    // The scrim is the token's own 40% pair, and the page behind it holds still.
    expect((dialog.parentElement as HTMLElement).className).toContain("bg-scrim");
    expect(document.body.style.overflow).toBe("hidden");

    // Exactly three fields: the title, the five pills, the word slider.
    expect(within(dialog).getAllByRole("textbox")).toHaveLength(1);
    expect(within(dialog).getAllByRole("slider")).toHaveLength(1);
    const group = within(dialog).getByRole("group");
    expect(within(group).getAllByRole("button")).toHaveLength(5);
    // The inheritance note, verbatim — the draft's own sentence.
    expect(de["writing.shelf.dialog.inheritance"]).toBe(
      "Dramaturgie, KI-Rolle und Kanon-Strenge übernimmt das Buch aus deinen Atelier-Einstellungen — änderbar, sobald der Workspace da ist.",
    );
    expect(within(dialog).getByText(de["writing.shelf.dialog.inheritance"])).toBeTruthy();
    // The CTA waits for a standing title; Abbrechen stands beside it.
    expect(createButton(dialog).hasAttribute("disabled")).toBe(true);
    expect(within(dialog).getByRole("button", { name: de["writing.shelf.dialog.cancel"] })).toBeTruthy();
    // On short viewports the body is the scroll region; the footer with
    // the actions stays pinned outside it, never below the fold.
    const scroll = dialog.querySelector(".overflow-y-auto") as HTMLElement;
    expect(scroll.contains(titleField(dialog))).toBe(true);
    expect(scroll.contains(dialog.querySelector("footer") as HTMLElement)).toBe(false);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.body.style.overflow).toBe("");
  });

  it("the title rides the cover live; the CTA and the error follow the trimmed title", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openNewBook();
    // Step 1's deterministic validation: the missing-title line stands while
    // the title is empty, and the cover speaks the honest untitled face.
    expect(within(dialog).getByText(de["writing.shelf.dialog.titleError"])).toBeTruthy();
    expect(titleField(dialog).getAttribute("aria-invalid")).toBe("true");
    expect(coverOf(dialog).textContent).toContain(de["writing.shelf.dialog.coverUntitled"]);
    expect(coverOf(dialog).getAttribute("style")).toContain("224px");

    fireEvent.change(titleField(dialog), { target: { value: "Die Winterchronik" } });
    expect(coverOf(dialog).textContent).toContain("Die Winterchronik");
    expect(within(dialog).queryByText(de["writing.shelf.dialog.titleError"])).toBeNull();
    expect(createButton(dialog).hasAttribute("disabled")).toBe(false);

    // Whitespace is no title — the draft's trim discipline, both faces back.
    fireEvent.change(titleField(dialog), { target: { value: "   " } });
    expect(createButton(dialog).hasAttribute("disabled")).toBe(true);
    expect(within(dialog).getByText(de["writing.shelf.dialog.titleError"])).toBeTruthy();
    expect(coverOf(dialog).textContent).toContain(de["writing.shelf.dialog.coverUntitled"]);
  });

  it("the genre pills multi-select under the 80-char cap and tint the cover", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openNewBook();
    const pill = (key: keyof typeof de) => within(dialog).getByRole("button", { name: de[key] });
    const scifi = pill("writing.shelf.dialog.genre.scifi");
    const mystery = pill("writing.shelf.dialog.genre.mystery");
    const historical = pill("writing.shelf.dialog.genre.historical");
    const literary = pill("writing.shelf.dialog.genre.literary");

    expect(scifi.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(scifi);
    expect(scifi.getAttribute("aria-pressed")).toBe("true");
    expect(coverOf(dialog).getAttribute("data-channel")).toBe("scifi");
    fireEvent.click(mystery);
    fireEvent.click(historical);
    // 65 chars stand; the fourth and fifth would overflow — disabled, noted.
    expect(literary.hasAttribute("disabled")).toBe(true);
    expect(pill("writing.shelf.dialog.genre.lowfantasy").hasAttribute("disabled")).toBe(true);
    expect(within(dialog).getByText(t("writing.shelf.dialog.genreCapNote", { cap: 80 }))).toBeTruthy();
    // Removing a selection frees the cap again — never a dropped choice.
    fireEvent.click(historical);
    expect(literary.hasAttribute("disabled")).toBe(false);
    expect(within(dialog).queryByText(t("writing.shelf.dialog.genreCapNote", { cap: 80 }))).toBeNull();
    // The cover follows the first selected pill; none left, the neutral linen.
    fireEvent.click(scifi);
    fireEvent.click(mystery);
    expect(coverOf(dialog).getAttribute("data-channel")).toBe("fallback");
  });

  it("the word target defaults to 65.000 with its format category and Normseiten", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openNewBook();
    const slider = within(dialog).getByRole("slider") as HTMLInputElement;
    expect(slider.value).toBe("65000");
    expect(within(dialog).getByText("65.000")).toBeTruthy();
    expect(within(dialog).getByText(de["writing.shelf.dialog.band.novel"])).toBeTruthy();
    expect(within(dialog).getByText(`(${de["writing.shelf.dialog.range.novel"]})`)).toBeTruthy();
    expect(within(dialog).getByText(t("writing.shelf.dialog.normseiten", { count: 240 }))).toBeTruthy();

    fireEvent.change(slider, { target: { value: "30000" } });
    expect(within(dialog).getByText("30.000")).toBeTruthy();
    expect(within(dialog).getByText(de["writing.shelf.dialog.band.novella"])).toBeTruthy();
    expect(within(dialog).getByText(t("writing.shelf.dialog.normseiten", { count: 111 }))).toBeTruthy();
    // The scale mark of the active band wears the primary ink.
    expect(within(dialog).getByText(de["writing.shelf.dialog.scale.novella"]).className).toContain("text-primary");
  });
});

describe("the shelf — the dialog creates for real and closes honestly", () => {
  it("Anlegen posts exactly the three answers; the refetch grows the shelf", async () => {
    scriptCreate();
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openNewBook();
    fireEvent.change(titleField(dialog), { target: { value: "  Die Winterchronik von Station Sieben  " } });
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.dialog.genre.scifi"] }));
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.dialog.genre.mystery"] }));
    fireEvent.change(within(dialog).getByRole("slider"), { target: { value: "80000" } });
    fireEvent.click(createButton(dialog));

    await waitFor(() => expect(api.POST).toHaveBeenCalledWith("/api/writing/novels", {
      body: {
        title: "Die Winterchronik von Station Sieben",
        genre: "Science Fiction & Speculative, Mystery & Noir",
        target_words: 80000,
      },
    }));
    // The dialog's answers never write wizard settings — three keys, no more.
    const body = (api.POST.mock.calls as unknown as [string, { body: Record<string, unknown> }][])
      .find(([path]) => path === "/api/writing/novels")?.[1].body;
    expect(Object.keys(body ?? {}).sort()).toEqual(["genre", "target_words", "title"]);

    // The dialog closes; the shelf's own refetch carries the new book — the
    // newest updated_at leads as the hero, the honest outcome of the column.
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(await screen.findByRole("heading", { level: 2, name: CREATED.title })).toBeTruthy();
    expect(screen.getByText(t("writing.shelf.metrics.books", { count: 5 }))).toBeTruthy();
    expect(screen.getAllByRole("article")).toHaveLength(4);
  });

  it("the CTA names its busy state and holds the dialog while the ask runs", async () => {
    let resolveCreate!: (answer: { data: unknown; response: Response }) => void;
    createAnswer = () =>
      new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveCreate = resolve;
      });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openNewBook();
    fireEvent.change(titleField(dialog), { target: { value: "Die Winterchronik" } });
    fireEvent.click(createButton(dialog));
    const busy = await within(dialog).findByRole("button", { name: de["writing.shelf.dialog.busy"] });
    expect(busy.hasAttribute("disabled")).toBe(true);
    expect(within(dialog).getByRole("button", { name: de["writing.shelf.dialog.cancel"] }).hasAttribute("disabled")).toBe(true);

    // Nothing closes mid-flight: Escape, the scrim and Abbrechen all wait.
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.click(dialog.parentElement as HTMLElement);
    expect(screen.getByRole("dialog")).toBeTruthy();

    resolveCreate({ data: CREATED, response: new Response(null, { status: 201 }) });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("a refusal keeps every answer and offers the family's retry", async () => {
    let attempts = 0;
    createAnswer = async (body) => {
      attempts += 1;
      if (attempts === 1) return { data: undefined, response: new Response(null, { status: 503 }) };
      novelsAnswer = async () => ({ data: [CREATED, ...SHELF_ROWS], response: ok() });
      return { data: { ...CREATED, title: body.title ?? CREATED.title }, response: new Response(null, { status: 201 }) };
    };
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openNewBook();
    fireEvent.change(titleField(dialog), { target: { value: "Die Winterchronik" } });
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.dialog.genre.mystery"] }));
    fireEvent.click(createButton(dialog));

    const alert = await within(dialog).findByRole("alert");
    expect(alert.textContent).toContain(de["writing.shelf.dialog.error"]);
    // The real refusal rides the line — never an invented gateway story.
    expect(alert.textContent).toContain("503");
    // The error stands in the pinned foot, outside the scroll region: on a
    // short viewport the reader hears it and sees it at once, no scroll owed.
    const scrollRegion = dialog.querySelector(".overflow-y-auto") as HTMLElement;
    expect(scrollRegion.contains(alert)).toBe(false);
    const foot = dialog.querySelector("footer") as HTMLElement;
    expect(foot.parentElement?.contains(alert)).toBe(true);
    // State preserved: the answers stand exactly as typed.
    expect((titleField(dialog) as HTMLInputElement).value).toBe("Die Winterchronik");
    expect(
      within(dialog).getByRole("button", { name: de["writing.shelf.dialog.genre.mystery"] }).getAttribute("aria-pressed"),
    ).toBe("true");

    fireEvent.click(within(alert).getByRole("button", { name: de["writing.shelf.error.retry"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(attempts).toBe(2);
    expect(await screen.findByRole("heading", { level: 2, name: CREATED.title })).toBeTruthy();
  });

  it("the retry never idles — it waits for the same standing title as the CTA", async () => {
    createAnswer = async () => ({ data: undefined, response: new Response(null, { status: 503 }) });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openNewBook();
    fireEvent.change(titleField(dialog), { target: { value: "Die Winterchronik" } });
    fireEvent.click(createButton(dialog));
    const alert = await within(dialog).findByRole("alert");
    const retry = within(alert).getByRole("button", { name: de["writing.shelf.error.retry"] });
    expect(retry.hasAttribute("disabled")).toBe(false);

    // Clearing the title disarms the retry exactly as it disarms the CTA —
    // the button never promises an ask the completeness guard would eat.
    fireEvent.change(titleField(dialog), { target: { value: "   " } });
    expect(retry.hasAttribute("disabled")).toBe(true);
    expect(createButton(dialog).hasAttribute("disabled")).toBe(true);
    fireEvent.click(retry);
    expect(api.POST).toHaveBeenCalledTimes(1);

    // A standing title arms it again; the error and the answers stand.
    fireEvent.change(titleField(dialog), { target: { value: "Die Winterchronik" } });
    expect(retry.hasAttribute("disabled")).toBe(false);
    expect(alert.textContent).toContain("503");
  });

  it("Escape, the scrim, Abbrechen and the cross close — focus returns to the opener", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    const opener = topNewBook();

    // Opening lands focus on the title field, the wizard's own first move.
    let dialog = openNewBook(opener);
    expect(document.activeElement).toBe(titleField(dialog));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);

    dialog = openNewBook(opener);
    fireEvent.click(dialog.parentElement as HTMLElement);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);

    dialog = openNewBook(opener);
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.dialog.cancel"] }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);

    dialog = openNewBook(opener);
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.dialog.close"] }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
    // A click inside the panel is no scrim press — the dialog stands.
    dialog = openNewBook(opener);
    fireEvent.click(dialog);
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("focus stays inside the dialog — Tab wraps at both ends", async () => {
    const user = userEvent.setup();
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    const dialog = openNewBook();
    fireEvent.change(titleField(dialog), { target: { value: "Die Winterchronik" } });
    const close = within(dialog).getByRole("button", { name: de["writing.shelf.dialog.close"] });
    const cta = createButton(dialog);

    // From the last live control, Tab wraps to the first; Shift+Tab back.
    cta.focus();
    await user.tab();
    expect(document.activeElement).toBe(close);
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(cta);
    // A whole round never leaves the panel.
    for (let at = 0; at < 12; at += 1) {
      await user.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
  });

  it("the dialog's state is transient — a reopen starts from the draft's defaults", async () => {
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });

    let dialog = openNewBook();
    fireEvent.change(titleField(dialog), { target: { value: "Verworfen" } });
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.dialog.genre.scifi"] }));
    fireEvent.change(within(dialog).getByRole("slider"), { target: { value: "120000" } });
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.dialog.cancel"] }));

    dialog = openNewBook();
    expect((titleField(dialog) as HTMLInputElement).value).toBe("");
    expect(
      within(dialog).getByRole("button", { name: de["writing.shelf.dialog.genre.scifi"] }).getAttribute("aria-pressed"),
    ).toBe("false");
    expect((within(dialog).getByRole("slider") as HTMLInputElement).value).toBe("65000");
  });

  it("creating from the empty shelf lands focus on the stable top-bar door", async () => {
    novelsAnswer = async () => ({ data: [], response: ok() });
    scriptCreate();
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dein erstes Buch wartet." });

    // The empty panel's own door opens the dialog; after the create the
    // panel is gone, so focus lands on the door that survives the refetch.
    const doors = screen.getAllByRole("button", { name: de["writing.shelf.newBook"] });
    const dialog = openNewBook(doors[1]);
    fireEvent.change(titleField(dialog), { target: { value: CREATED.title } });
    fireEvent.click(createButton(dialog));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(await screen.findByRole("heading", { level: 2, name: CREATED.title })).toBeTruthy();
    expect(screen.queryByText("Dein erstes Buch wartet.")).toBeNull();
    expect(document.activeElement).toBe(topNewBook());
  });
});

describe("the shelf — the streak chip and the banner ride the real aggregate", () => {
  it("a zero streak is an honest 0 — never hidden, never a dash", async () => {
    activityAnswer = async () => ({ data: activityRow({ streak_days: 0 }), response: ok() });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    expect(screen.getByText(t("writing.shelf.metrics.streak", { count: 0 }))).toBeTruthy();
  });

  it("an unreachable aggregate leaves the chip neutral — the shelf still stands", async () => {
    activityAnswer = async () => ({ data: undefined, response: new Response(null, { status: 503 }) });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    const chipValue = screen
      .getByText(de["writing.shelf.metrics.streakLabel"])
      .parentElement?.firstElementChild;
    expect(chipValue?.textContent).toBe("—");
    // The banner's own retry family stands beside the live shelf.
    expect(screen.getByRole("alert").textContent).toContain(de["writing.shelf.banner.error.title"]);
    expect(screen.getByRole("button", { name: de["writing.shelf.error.retry"] })).toBeTruthy();
  });

  it("a shelf write refetches the aggregate — the banner moves with the day's words", async () => {
    // The invalidation family's live pin: the archive write goes through
    // invalidateNovelShelf, which asks the activity key again — the same
    // door a chapter write moves the banner through (Task 4's write path).
    let calls = 0;
    activityAnswer = async () => {
      calls += 1;
      const today = calls === 1 ? 412 : 900;
      return {
        data: activityRow({
          today_words: today,
          points: [...ACTIVITY_POINTS.slice(0, 29), { date: ACTIVITY_POINTS[29].date, words: today }],
        }),
        response: ok(),
      };
    };
    archiveAnswer = async (_id, body) => ({
      data: { ...SECOND, archived_at: body.archived_at },
      response: ok(),
    });
    renderShelf();
    await screen.findByRole("heading", { level: 2, name: "Dead Signal" });
    expect(screen.getByText(/Du hast heute bereits 412 Wörter verfasst\./)).toBeTruthy();
    novelsAnswer = async () => ({ data: [HERO, THIRD, FOURTH], response: ok() });

    const dialog = openMenu("Winterhaus");
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.shelf.menu.archive"] }));
    const confirm = screen.getByRole("dialog");
    fireEvent.click(within(confirm).getByRole("button", { name: de["writing.shelf.menu.archive"] }));

    await waitFor(() => expect(calls).toBe(2));
    expect(await screen.findByText(/Du hast heute bereits 900 Wörter verfasst\./)).toBeTruthy();
  });
});
