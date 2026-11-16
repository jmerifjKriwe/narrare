// @vitest-environment jsdom
/**
 * The activity banner (Task 10) — the `shelf` draft's cadence panel wired to
 * the real aggregate. Rendered directly under the one query client with only
 * the API client mocked at its module boundary; the mock keeps the backend's
 * contract (ActivityRead, zero-days dense, UTC day boundary). Every case
 * renders German and asserts the du-tone copy the catalog carries: the five
 * data shapes (populated, mixed, empty, loading, error), the goal pair only
 * when the hero carries a target, the sparkline's path the pure helper's own,
 * and the retry family that holds its notice while it asks again.
 */
import { QueryClientProvider } from "@tanstack/react-query";
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

import { client, type Activity, type Novel } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { t } from "@shell/lib/i18n";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { sparkline } from "./activity";
import { ShelfBanner } from "./ShelfBanner";

const api = client as unknown as Record<"GET", ReturnType<typeof vi.fn>>;
const de = catalogs.de;

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** A novel row as the API answers it — the hero the banner's goal reads. */
function novelRow(overrides: Partial<Novel> & { id: string; title: string }): Novel {
  return {
    genre: null,
    blurb: null,
    author: null,
    language: null,
    chapter_count: 0,
    word_count: 0,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-14T14:22:00Z",
    last_exported_at: null,
    status: null,
    series_title: null,
    series_volume: null,
    archived_at: null,
    target_words: null,
    ...overrides,
  };
}

const HERO = novelRow({
  id: "11111111-1111-1111-1111-111111111111",
  title: "Dead Signal",
  word_count: 48342,
  target_words: 65000,
});

/** Thirty days, zero-days dense, the last three written — today 412. */
const WORDS30 = [
  0, 0, 120, 0, 340, 0, 0, 180, 0, 0, 0, 260, 0, 0, 90, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 180, 260, 412,
];
const POINTS30 = WORDS30.map((words, at) => ({
  date: `2026-10-${String(at + 1).padStart(2, "0")}`,
  words,
}));

function activityRow(overrides: Partial<Activity> = {}): Activity {
  return {
    points: POINTS30,
    streak_days: 3,
    weekly_average: 840,
    today_words: 412,
    ...overrides,
  };
}

/** What the activity endpoint answers; a test may script a failure or a gap. */
let activityAnswer: () => Promise<{ data?: unknown; response: Response }> = async () => ({
  data: activityRow(),
  response: ok(),
});

function renderBanner(hero: Novel | null = HERO) {
  return render(
    <QueryClientProvider client={queryClient}>
      <ShelfBanner hero={hero} noteId="banner-note" />
    </QueryClientProvider>,
  );
}

/** The banner's own section — the one this harness renders. */
const banner = () => document.querySelector("section") as HTMLElement;

beforeEach(() => {
  activityAnswer = async () => ({ data: activityRow(), response: ok() });
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/writing/activity") return activityAnswer();
    throw new Error(`unexpected request: ${path}`);
  });
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  applyLocale("de");
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

describe("the banner — a populated window speaks the aggregate's own figures", () => {
  it("asks the aggregate on mount, the default window in its bare shape", async () => {
    renderBanner();
    await screen.findByText(t("writing.shelf.banner.goal", { title: HERO.title }));
    // days=30 is the server's own default — the ask keeps the bare shape.
    expect(api.GET).toHaveBeenCalledWith("/api/writing/activity");
  });

  it("the goal line is the hero's own pair — the active book's goal, disclosed", async () => {
    renderBanner();
    const heading = await screen.findByRole("heading", { level: 3 });
    expect(heading.textContent).toBe(
      `${t("writing.shelf.banner.goal", { title: "Dead Signal" })}: ${t("writing.shelf.words.pair", { count: 48342, target: 65000 })}`,
    );
    // 65.000 − 48.342 — the draft's second sentence, the book goal's remainder.
    expect(heading.textContent).toContain("48.342 / 65.000 Wörter");
  });

  it("today's words stand where the draft places them, with the goal's remainder", async () => {
    renderBanner();
    await screen.findByText(t("writing.shelf.banner.goal", { title: HERO.title }));
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toBe(
      `Du hast heute bereits 412 Wörter verfasst. Noch 16.658 Wörter bis zum Ziel.`,
    );
  });

  it("the weekly average is the API's number at one decimal, de-DE grouped", async () => {
    renderBanner();
    await screen.findByText(t("writing.shelf.banner.goal", { title: HERO.title }));
    expect(screen.getByText(de["writing.shelf.banner.weekly"])).toBeTruthy();
    expect(screen.getByText("840,0 W/Tag")).toBeTruthy();
  });

  it("the sparkline is the helper's own path — thirty points, today marked, UTC named", async () => {
    renderBanner();
    await screen.findByText(t("writing.shelf.banner.goal", { title: HERO.title }));
    const figure = screen.getByRole("img");
    expect(figure.getAttribute("aria-label")).toBe(
      t("writing.shelf.banner.sparkline", { days: 30 }),
    );
    expect(figure.getAttribute("aria-label")).toContain("UTC");
    expect(figure.getAttribute("viewBox")).toBe("0 0 120 32");
    expect(figure.getAttribute("class")).toContain("text-area-writing");
    const path = figure.querySelector("path");
    expect(path?.getAttribute("d")).toBe(sparkline(POINTS30)?.d);
    expect(path?.getAttribute("stroke")).toBe("currentColor");
    expect(path?.getAttribute("stroke-width")).toBe("2");
    expect(path?.getAttribute("fill")).toBe("none");
    const dot = figure.querySelector("circle");
    const today = sparkline(POINTS30)?.today;
    expect(dot?.getAttribute("cx")).toBe(String(today?.x));
    expect(dot?.getAttribute("cy")).toBe(String(today?.y));
  });

  it("the statistics door stays honestly disabled with the drafted note", async () => {
    renderBanner();
    await screen.findByText(t("writing.shelf.banner.goal", { title: HERO.title }));
    const door = screen.getByRole("button", { name: de["writing.shelf.banner.stats"] });
    expect(door.hasAttribute("disabled")).toBe(true);
    const noteId = door.getAttribute("aria-describedby");
    expect(document.getElementById(noteId as string)?.textContent).toBe(de["writing.shelf.comingSoon"]);
  });
});

describe("the banner — a mixed window stays honest, negative days and all", () => {
  it("a negative today speaks the removal voice, the number unfloored", async () => {
    activityAnswer = async () => ({
      data: activityRow({ today_words: -120, weekly_average: -12.5 }),
      response: ok(),
    });
    renderBanner();
    await screen.findByText(t("writing.shelf.banner.goal", { title: HERO.title }));
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toContain(
      "Heute hast du mehr Text entfernt als hinzugefügt — dein Tag steht bei -120 Wörtern.",
    );
    // The average rides the same honesty: one decimal, the sign intact.
    expect(screen.getByText("-12,5 W/Tag")).toBeTruthy();
  });

  it("zero-days and a negative day draw the true scale — the helper's path again", async () => {
    const words = [...WORDS30];
    words[10] = -60;
    const points = words.map((words_, at) => ({
      date: `2026-10-${String(at + 1).padStart(2, "0")}`,
      words: words_,
    }));
    activityAnswer = async () => ({ data: activityRow({ points }), response: ok() });
    renderBanner();
    await screen.findByText(t("writing.shelf.banner.goal", { title: HERO.title }));
    const path = screen.getByRole("img").querySelector("path");
    expect(path?.getAttribute("d")).toBe(sparkline(points)?.d);
    expect(path?.getAttribute("d")?.split(" L ")).toHaveLength(30);
  });

  it("a quiet today speaks the quiet voice — zero, never hidden", async () => {
    activityAnswer = async () => ({
      data: activityRow({ today_words: 0 }),
      response: ok(),
    });
    renderBanner();
    await screen.findByText(t("writing.shelf.banner.goal", { title: HERO.title }));
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toContain("Heute hast du noch keine Wörter verfasst.");
  });
});

describe("the banner — an empty window answers the drafted neutral", () => {
  const EMPTY = activityRow({
    points: Array.from({ length: 30 }, (_, at) => ({
      date: `2026-10-${String(at + 1).padStart(2, "0")}`,
      words: 0,
    })),
    streak_days: 0,
    weekly_average: 0,
    today_words: 0,
  });

  it("no rows ever: the neutral copy, no invented values, the flat honest line", async () => {
    activityAnswer = async () => ({ data: EMPTY, response: ok() });
    renderBanner();
    expect(await screen.findByText(de["writing.shelf.banner.body"])).toBeTruthy();
    // The neutral stands alone — no today sentence, no remainder beside it.
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toBe(de["writing.shelf.banner.body"]);
    // The book's goal is the book's truth, independent of the empty window.
    expect(screen.getByRole("heading", { level: 3 }).textContent).toContain(
      t("writing.shelf.words.pair", { count: 48342, target: 65000 }),
    );
    // The API's zeros are real figures: the average 0,0 and the flat line.
    expect(screen.getByText("0,0 W/Tag")).toBeTruthy();
    const path = screen.getByRole("img").querySelector("path");
    expect(path?.getAttribute("d")).toBe(sparkline(EMPTY.points)?.d);
    expect(path?.getAttribute("d")).toContain("M 0,16");
  });

  it("an empty window without a target keeps the dash — no noTarget pile-on", async () => {
    activityAnswer = async () => ({ data: EMPTY, response: ok() });
    renderBanner({ ...HERO, target_words: null });
    expect(await screen.findByText(de["writing.shelf.banner.body"])).toBeTruthy();
    const heading = screen.getByRole("heading", { level: 3 });
    expect(heading.textContent).toBe(
      `${t("writing.shelf.banner.goal", { title: "Dead Signal" })}: —`,
    );
    expect(banner().querySelector("p.text-meta")?.textContent).toBe(de["writing.shelf.banner.body"]);
  });

  it("an empty window without a hero names no goal at all", async () => {
    activityAnswer = async () => ({ data: EMPTY, response: ok() });
    renderBanner(null);
    expect(await screen.findByText(de["writing.shelf.banner.noGoal"])).toBeTruthy();
    expect(screen.getByText(de["writing.shelf.banner.body"])).toBeTruthy();
  });
});

describe("the banner — loading stands in the shelf's skeleton family", () => {
  it("while the ask is outstanding the bones pulse — nothing invented", async () => {
    let resolveActivity!: (answer: { data: unknown; response: Response }) => void;
    activityAnswer = () =>
      new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveActivity = resolve;
      });
    const { container } = renderBanner();
    await waitFor(() => expect(api.GET).toHaveBeenCalledWith("/api/writing/activity"));

    // The skeleton family: the soft token's pulse, no figures, no curve.
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThanOrEqual(3);
    for (const bone of container.querySelectorAll(".animate-pulse")) {
      expect(bone.className).toContain("bg-soft");
      expect(bone.getAttribute("aria-hidden")).toBe("true");
    }
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.queryByText(/Wörter/)).toBeNull();
    // The chrome stands: the weekly eyebrow and the disabled statistics door.
    expect(screen.getByText(de["writing.shelf.banner.weekly"])).toBeTruthy();
    expect(
      screen.getByRole("button", { name: de["writing.shelf.banner.stats"] }).hasAttribute("disabled"),
    ).toBe(true);

    resolveActivity({ data: activityRow(), response: ok() });
    expect(await screen.findByText(t("writing.shelf.banner.goal", { title: HERO.title }))).toBeTruthy();
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(0);
  });
});

describe("the banner — error answers the honest retry family", () => {
  it("an unreachable aggregate names the failure and offers a working retry", async () => {
    let attempts = 0;
    activityAnswer = async () => {
      attempts += 1;
      if (attempts === 1) return { data: undefined, response: new Response(null, { status: 503 }) };
      return { data: activityRow(), response: ok() };
    };
    renderBanner();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(de["writing.shelf.banner.error.title"]);
    // The real status rides the message — never an invented gateway story.
    expect(alert.textContent).toContain("503");
    expect(alert.textContent).toContain(de["writing.shelf.banner.error.body"]);
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText("—")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.error.retry"] }));
    expect(await screen.findByText(t("writing.shelf.banner.goal", { title: HERO.title }))).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(attempts).toBe(2);
  });

  it("the retry holds its notice with a busy label — no skeleton flash mid-retry", async () => {
    let attempts = 0;
    let resolveSecond!: (answer: { data: unknown; response: Response }) => void;
    activityAnswer = async () => {
      attempts += 1;
      if (attempts === 1) return { data: undefined, response: new Response(null, { status: 503 }) };
      return new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveSecond = resolve;
      });
    };
    const { container } = renderBanner();
    await screen.findByRole("alert");

    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.error.retry"] }));
    const busy = await screen.findByRole("button", { name: de["writing.shelf.error.retrying"] });
    expect(busy.hasAttribute("disabled")).toBe(true);
    // The notice stands — the query's pending never flashes the bones.
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(0);

    resolveSecond({ data: activityRow(), response: ok() });
    expect(await screen.findByText(t("writing.shelf.banner.goal", { title: HERO.title }))).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("the banner — the goal pair stands only when the target is real", () => {
  it("a missing target keeps the dash and names the missing goal once", async () => {
    renderBanner({ ...HERO, target_words: null });
    const heading = await screen.findByRole("heading", { level: 3 });
    expect(heading.textContent).toBe(
      `${t("writing.shelf.banner.goal", { title: "Dead Signal" })}: —`,
    );
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toBe(
      `Du hast heute bereits 412 Wörter verfasst. ${de["writing.shelf.noTarget"]}`,
    );
    expect(heading.textContent).not.toContain("/");
  });

  it("a zero target is no target — the progress rule's own neutral", async () => {
    renderBanner({ ...HERO, target_words: 0 });
    const heading = await screen.findByRole("heading", { level: 3 });
    expect(heading.textContent).toContain(": —");
  });

  it("no hero names no goal — the today line still speaks the atelier", async () => {
    renderBanner(null);
    expect(await screen.findByText(de["writing.shelf.banner.noGoal"])).toBeTruthy();
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toBe("Du hast heute bereits 412 Wörter verfasst.");
    // No goal pair — the pair's spaced slash stands nowhere (the average's
    // „W/Tag" unit is its own word, not a pair).
    expect(screen.queryByText(/ \/ /)).toBeNull();
  });

  it("a finished book carries the pair without a remainder — nothing left to owe", async () => {
    renderBanner({ ...HERO, word_count: 70000 });
    const heading = await screen.findByRole("heading", { level: 3 });
    expect(heading.textContent).toContain(
      t("writing.shelf.words.pair", { count: 70000, target: 65000 }),
    );
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toBe("Du hast heute bereits 412 Wörter verfasst.");
  });
});

describe("the banner — the copy speaks the catalog's du-tone German", () => {
  it("the populated face is the catalog's own, not an English fallback", async () => {
    renderBanner();
    await screen.findByText(t("writing.shelf.banner.goal", { title: HERO.title }));
    expect(screen.getByText("Ziel für ‚Dead Signal‘")).toBeTruthy();
    expect(screen.getByText(/Du hast heute bereits 412 Wörter verfasst\./)).toBeTruthy();
    expect(screen.getByText(/Noch 16\.658 Wörter bis zum Ziel\./)).toBeTruthy();
    expect(screen.getByText("Wochenschnitt")).toBeTruthy();
    expect(screen.getByText("Statistiken öffnen")).toBeTruthy();
    expect(within(banner()).queryByText(/Today|Goal for|Weekly/)).toBeNull();
  });
});
