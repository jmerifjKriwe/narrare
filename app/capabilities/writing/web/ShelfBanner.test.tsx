// @vitest-environment jsdom
/**
 * The activity banner (Task 10, W4 Task 9) — the `shelf` draft's cadence
 * panel wired to the real aggregate. Rendered directly under the one query
 * client with only the API client mocked at its module boundary; the mock
 * keeps the backend's contract (ActivityRead, zero-days dense, UTC day
 * boundary, the goal progress the aggregate derives). Every case renders
 * German and asserts the du-tone copy the catalog carries: the five data
 * shapes (populated, mixed, empty, loading, error), the daily goal's three
 * faces (set, unset, reached — gap row 25), the sparkline's path the pure
 * helper's own, and the retry family that holds its notice while it asks
 * again. The hero-book pin is gone: the banner reads the atelier's goal,
 * no book title and no book pair stand in it.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

// Full-suite load: see WorkspacePage.test.tsx.
configure({ asyncUtilTimeout: 5000 });
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

import { client, type Activity } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { t } from "@shell/lib/i18n";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { sparkline } from "./activity";
import { ShelfBanner } from "./ShelfBanner";

const api = client as unknown as Record<"GET", ReturnType<typeof vi.fn>>;
const de = catalogs.de;

// The disabled statistics door names its state, not a shared-CTA promise
// (#979). The banner key is separate from writing.shelf.comingSoon, which
// stays on the shelf's live-CTA-adjacent notes.
const STATUS_NOTE = {
  en: "Not available yet.",
  de: "Noch nicht verfügbar.",
  fr: "Pas encore disponible.",
} as const;

const FUTURE_PROMISE =
  /build-out|aufbau|wave|welle|vague|appear|erschein|appara|coming soon|kommt mit|arrive avec|future|becomes available|later|options/i;

describe("the banner status note speaks to the reader", () => {
  it("is status-only in every catalog, never a future promise", () => {
    for (const locale of ["en", "de", "fr"] as const) {
      const note = catalogs[locale]["writing.shelf.banner.statsNote"];
      expect(note).toBe(STATUS_NOTE[locale]);
      expect(note).not.toMatch(FUTURE_PROMISE);
    }
  });
});

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** Thirty days, zero-days dense, the last three written — today 412. */
const WORDS30 = [
  0, 0, 120, 0, 340, 0, 0, 180, 0, 0, 0, 260, 0, 0, 90, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 180, 260, 412,
];
const POINTS30 = WORDS30.map((words, at) => ({
  date: `2026-10-${String(at + 1).padStart(2, "0")}`,
  words,
}));

/** The aggregate as the API answers it — the draft's own goal figures:
 *  750 stored, 412 written today, 338 remaining (gap row 25's draft). */
function activityRow(overrides: Partial<Activity> = {}): Activity {
  return {
    points: POINTS30,
    streak_days: 3,
    weekly_average: 840,
    today_words: 412,
    daily_goal_words: 750,
    goal_met: false,
    goal_remaining: 338,
    ...overrides,
  };
}

/** What the activity endpoint answers; a test may script a failure or a gap. */
let activityAnswer: () => Promise<{ data?: unknown; response: Response }> = async () => ({
  data: activityRow(),
  response: ok(),
});

function renderBanner() {
  return render(
    <QueryClientProvider client={queryClient}>
      <ShelfBanner noteId="banner-note" />
    </QueryClientProvider>,
  );
}

/** The banner's own section — the one this harness renders. */
const banner = () => document.querySelector("section") as HTMLElement;

/** The goal heading's anchor — the daily-goal label span. */
const goalHeading = () => t("writing.shelf.banner.dailyGoal");

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
    await screen.findByText(goalHeading());
    // days=30 is the server's own default — the ask keeps the bare shape.
    expect(api.GET).toHaveBeenCalledWith("/api/writing/activity");
  });

  it("the goal line is the atelier's daily goal — the draft's own line", async () => {
    renderBanner();
    const heading = await screen.findByRole("heading", { level: 3 });
    expect(heading.textContent).toBe(
      `${goalHeading()}: ${t("writing.shelf.words.count", { count: 750 })}`,
    );
    // „Heutiges Schreibziel: 750 Wörter" — the figure in the tabular span.
    expect(heading.textContent).toBe("Heutiges Schreibziel: 750 Wörter");
    expect(heading.querySelector("span.tabular-nums")?.textContent).toBe(": 750 Wörter");
  });

  it("today's words stand where the draft places them, with the goal's remainder", async () => {
    renderBanner();
    await screen.findByText(goalHeading());
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toBe(
      `Du hast heute bereits 412 Wörter verfasst. Noch 338 Wörter bis zum Tagesziel.`,
    );
  });

  it("the weekly average is the API's number at one decimal, de-DE grouped", async () => {
    renderBanner();
    await screen.findByText(goalHeading());
    expect(screen.getByText(de["writing.shelf.banner.weekly"])).toBeTruthy();
    expect(screen.getByText("840,0 W/Tag")).toBeTruthy();
  });

  it("the sparkline is the helper's own path — thirty points, today marked, UTC named", async () => {
    renderBanner();
    await screen.findByText(goalHeading());
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
    await screen.findByText(goalHeading());
    const door = screen.getByRole("button", { name: de["writing.shelf.banner.stats"] });
    expect(door.hasAttribute("disabled")).toBe(true);
    const noteId = door.getAttribute("aria-describedby");
    expect(document.getElementById(noteId as string)?.textContent).toBe(
      de["writing.shelf.banner.statsNote"],
    );
  });

  it("the hero-book pin is gone — no book title, no book pair in the banner", async () => {
    renderBanner();
    await screen.findByText(goalHeading());
    // The W3 pin („Ziel für ‚…': … / … Wörter") ended with row 25: the
    // banner names no book and carries no spaced-slash pair (the average's
    // „W/Tag" unit is its own word, not a pair).
    expect(within(banner()).queryByText(/Ziel für/)).toBeNull();
    expect(within(banner()).queryByText(/ \/ /)).toBeNull();
  });
});

describe("the banner — a mixed window stays honest, negative days and all", () => {
  it("a negative today speaks the removal voice, the remainder owes the loss too", async () => {
    activityAnswer = async () => ({
      data: activityRow({ today_words: -120, weekly_average: -12.5, goal_remaining: 870 }),
      response: ok(),
    });
    renderBanner();
    await screen.findByText(goalHeading());
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toContain(
      "Heute hast du mehr Text entfernt als hinzugefügt — dein Tag steht bei -120 Wörtern.",
    );
    // 750 + 120 — the aggregate's own remainder, the net unfloored.
    expect(body?.textContent).toContain("Noch 870 Wörter bis zum Tagesziel.");
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
    await screen.findByText(goalHeading());
    const path = screen.getByRole("img").querySelector("path");
    expect(path?.getAttribute("d")).toBe(sparkline(points)?.d);
    expect(path?.getAttribute("d")?.split(" L ")).toHaveLength(30);
  });

  it("a quiet today speaks the quiet voice — the whole goal still owed", async () => {
    activityAnswer = async () => ({
      data: activityRow({ today_words: 0, goal_remaining: 750 }),
      response: ok(),
    });
    renderBanner();
    await screen.findByText(goalHeading());
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toBe(
      `Heute hast du noch keine Wörter verfasst. Noch 750 Wörter bis zum Tagesziel.`,
    );
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
    goal_remaining: 750,
  });

  it("no rows ever: the neutral copy, no invented values, the flat honest line", async () => {
    activityAnswer = async () => ({ data: EMPTY, response: ok() });
    renderBanner();
    expect(await screen.findByText(de["writing.shelf.banner.body"])).toBeTruthy();
    // The neutral stands alone — no today sentence, no remainder beside it.
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toBe(de["writing.shelf.banner.body"]);
    // The daily goal is the user's truth, independent of the empty window.
    expect(screen.getByRole("heading", { level: 3 }).textContent).toBe(
      "Heutiges Schreibziel: 750 Wörter",
    );
    // The API's zeros are real figures: the average 0,0 and the flat line.
    expect(screen.getByText("0,0 W/Tag")).toBeTruthy();
    const path = screen.getByRole("img").querySelector("path");
    expect(path?.getAttribute("d")).toBe(sparkline(EMPTY.points)?.d);
    expect(path?.getAttribute("d")).toContain("M 0,16");
  });

  it("an empty window without a goal keeps the honest unset heading", async () => {
    activityAnswer = async () => ({
      data: { ...EMPTY, daily_goal_words: null, goal_remaining: 0 },
      response: ok(),
    });
    renderBanner();
    expect(await screen.findByText(de["writing.shelf.banner.body"])).toBeTruthy();
    expect(screen.getByRole("heading", { level: 3 }).textContent).toBe(
      de["writing.shelf.banner.noGoal"],
    );
    expect(banner().querySelector("p.text-meta")?.textContent).toBe(de["writing.shelf.banner.body"]);
  });
});

describe("the banner — the daily goal's three faces (gap row 25)", () => {
  it("unset: the honest neutral heading, the today line alone — no goal copy", async () => {
    activityAnswer = async () => ({
      data: activityRow({ daily_goal_words: null, goal_met: false, goal_remaining: 0 }),
      response: ok(),
    });
    renderBanner();
    expect(await screen.findByText(de["writing.shelf.banner.noGoal"])).toBeTruthy();
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toBe("Du hast heute bereits 412 Wörter verfasst.");
    expect(screen.queryByText(/Tagesziel/)).toBeNull();
    expect(screen.queryByText(de["writing.shelf.banner.dailyMet"])).toBeNull();
  });

  it("open: the remainder reads the aggregate's own field, de-DE grouped", async () => {
    activityAnswer = async () => ({
      data: activityRow({ daily_goal_words: 20000, goal_remaining: 12345 }),
      response: ok(),
    });
    renderBanner();
    const heading = await screen.findByRole("heading", { level: 3 });
    expect(heading.textContent).toBe("Heutiges Schreibziel: 20.000 Wörter");
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toBe(
      `Du hast heute bereits 412 Wörter verfasst. Noch 12.345 Wörter bis zum Tagesziel.`,
    );
  });

  it("reached: the done-state copy stands, no remainder beside it", async () => {
    activityAnswer = async () => ({
      data: activityRow({ daily_goal_words: 400, goal_met: true, goal_remaining: 0 }),
      response: ok(),
    });
    renderBanner();
    const heading = await screen.findByRole("heading", { level: 3 });
    expect(heading.textContent).toBe("Heutiges Schreibziel: 400 Wörter");
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toBe(
      `Du hast heute bereits 412 Wörter verfasst. ${de["writing.shelf.banner.dailyMet"]}`,
    );
    expect(screen.queryByText(/Noch .* Wörter bis zum Tagesziel/)).toBeNull();
  });

  it("reached exactly at the goal is reached — the aggregate's mark decides", async () => {
    activityAnswer = async () => ({
      data: activityRow({ daily_goal_words: 412, goal_met: true, goal_remaining: 0 }),
      response: ok(),
    });
    renderBanner();
    await screen.findByText(goalHeading());
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toContain(de["writing.shelf.banner.dailyMet"]);
    expect(body?.textContent).not.toContain("bis zum Tagesziel");
  });

  it("the unset neutral wins over any progress field — presence decides", async () => {
    // A stale remainder beside a null goal is no goal: the banner reads
    // the stored answer's presence first, never the progress alone.
    activityAnswer = async () => ({
      data: activityRow({ daily_goal_words: null, goal_met: false, goal_remaining: 338 }),
      response: ok(),
    });
    renderBanner();
    expect(await screen.findByText(de["writing.shelf.banner.noGoal"])).toBeTruthy();
    const body = banner().querySelector("p.text-meta");
    expect(body?.textContent).toBe("Du hast heute bereits 412 Wörter verfasst.");
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
    expect(await screen.findByText(goalHeading())).toBeTruthy();
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
    expect(await screen.findByText(goalHeading())).toBeTruthy();
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
    expect(await screen.findByText(goalHeading())).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("the banner — the copy speaks the catalog's du-tone German", () => {
  it("the populated face is the catalog's own, not an English fallback", async () => {
    renderBanner();
    await screen.findByText(goalHeading());
    expect(screen.getByText("Heutiges Schreibziel")).toBeTruthy();
    expect(screen.getByText(/Du hast heute bereits 412 Wörter verfasst\./)).toBeTruthy();
    expect(screen.getByText(/Noch 338 Wörter bis zum Tagesziel\./)).toBeTruthy();
    expect(screen.getByText("Wochenschnitt")).toBeTruthy();
    expect(screen.getByText("Statistiken öffnen")).toBeTruthy();
    expect(within(banner()).queryByText(/Today|Goal for|Weekly/)).toBeNull();
    // The dead pin's copy stands nowhere — the hero-book goal ended.
    expect(within(banner()).queryByText(/Ziel für/)).toBeNull();
  });

  it("the reached face speaks the done-state copy, du-tone", async () => {
    activityAnswer = async () => ({
      data: activityRow({ daily_goal_words: 400, goal_met: true, goal_remaining: 0 }),
      response: ok(),
    });
    renderBanner();
    await screen.findByText(goalHeading());
    expect(screen.getByText(/Tagesziel erreicht\./)).toBeTruthy();
  });
});
