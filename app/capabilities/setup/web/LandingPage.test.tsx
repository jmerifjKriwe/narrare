// @vitest-environment jsdom
/**
 * The post-setup landing — the `/` gate's complete branch — driven through
 * the real router over the real root route (the ProvisioningStep pattern).
 * Only the API client is mocked at its module boundary; the mock keeps the
 * backend's contract: the settings row exists once setup has run (it holds
 * the chosen locale, and a switcher PATCH writes it), the status answers
 * complete, and the novels list carries the one book setup bound. The hero
 * must speak that row's facts — never session storage, never an invented
 * progress — and every door the further build-out has not reached yet stays
 * honestly disabled with the drafted note.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
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

import { client } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { demos } from "@shell/lib/generated/demos";
import { t } from "@shell/lib/i18n";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

import { routes } from "./routes";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The novel row setup bound — the dead-signal demo path's facts. */
const NOVEL_ROW = {
  id: "11111111-1111-1111-1111-111111111111",
  title: "Dead Signal",
  genre: "Science Fiction",
  chapter_count: 3,
  word_count: 0,
  author: null,
  blurb: null,
  language: "en",
  created_at: "2026-11-14T10:00:00Z",
  updated_at: "2026-11-14T10:00:00Z",
  last_exported_at: null,
};

/** The settings row's locale, as the backend holds it: a switcher PATCH
 *  writes it and the invalidated refetch reads it back — the post-setup
 *  record, never the pre-setup mirror. */
let rowLocale: string | null = "de";
/** What the novels endpoint answers; a test may script a failure or a gap. */
let novelsAnswer: () => Promise<{ data?: unknown; response: Response }> = async () => ({
  data: [NOVEL_ROW],
  response: ok(),
});

function scriptApi() {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: rowLocale, theme: null }, response: ok() };
    }
    if (path === "/api/setup/status") {
      return { data: { complete: true }, response: ok() };
    }
    if (path === "/api/writing/novels") return novelsAnswer();
    throw new Error(`unexpected request: ${path}`);
  });
  api.PATCH.mockImplementation(async (path: string, init?: { body?: { locale?: string } }) => {
    if (path !== "/api/settings") throw new Error(`unexpected request: ${path}`);
    rowLocale = init?.body?.locale ?? null;
    return { data: { locale: rowLocale, theme: null }, response: ok() };
  });
}

function renderLanding() {
  const router = createRouter({
    routeTree: rootRoute.addChildren([...routes]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

/** The landing's controls, named by the German catalog the row holds. */
const de = catalogs.de;
const writeButton = () => screen.getByRole("button", { name: de["setup.landing.cta.write"] });
const loreButton = () => screen.getByRole("button", { name: de["setup.landing.cta.lore"] });
const storyboardButton = () =>
  screen.getByRole("button", { name: de["setup.landing.cta.storyboard"] });
const heroSection = () =>
  screen.getByRole("heading", { level: 1, name: NOVEL_ROW.title }).closest("section") as HTMLElement;

beforeEach(() => {
  rowLocale = "de";
  novelsAnswer = async () => ({ data: [NOVEL_ROW], response: ok() });
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

describe("the landing — the hero speaks the novel row's facts", () => {
  it("renders the row's title, genre and chapters — no invented progress", async () => {
    renderLanding();

    expect(await screen.findByRole("heading", { level: 1, name: "Dead Signal" })).toBeTruthy();
    // The meta line is the row's own genre and chapter count, neutral wording.
    expect(
      screen.getByText(t("setup.landing.meta", { genre: "Science Fiction", count: 3 })),
    ).toBeTruthy();
    expect(screen.getByText(de["setup.landing.eyebrow"])).toBeTruthy();
    // The honest word stand: counted at first write, never a percentage.
    expect(screen.getByText(new RegExp(de["setup.landing.wordStand"]))).toBeTruthy();
    expect(screen.getByText(de["setup.landing.progressRight"])).toBeTruthy();
    const hero = heroSection();
    expect(within(hero).queryByText(/%/)).toBeNull();
    // The progress track stands empty — the draft's sliver was its mock.
    const track = hero.querySelector(".bg-surface-container-highest");
    expect(track).not.toBeNull();
    expect(track?.childElementCount).toBe(0);
    // The book object wears the cover system at hero size, the row's facts.
    const cover = document.querySelector('[data-channel="scifi"]');
    expect(cover).not.toBeNull();
    expect(cover?.getAttribute("style")).toContain("192px");
    // The shelf's facts come from the novels query, not from any storage.
    expect(api.GET).toHaveBeenCalledWith("/api/writing/novels");
  });

  it("a blank novel answers honestly — no genre, zero chapters", async () => {
    novelsAnswer = async () => ({
      data: [{ ...NOVEL_ROW, title: "Der Klang des Eises", genre: null, chapter_count: 0 }],
      response: ok(),
    });
    renderLanding();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Der Klang des Eises" }),
    ).toBeTruthy();
    // No genre: the meta line carries the chapter count alone, zero included.
    expect(screen.getByText(t("setup.basis.demoChapters", { count: 0 }))).toBeTruthy();
    expect(screen.getByText(new RegExp(de["setup.landing.wordStand"]))).toBeTruthy();
  });

  it("names the tab and keeps the quote and the trust bar", async () => {
    renderLanding();
    await screen.findByRole("heading", { level: 1, name: "Dead Signal" });

    expect(document.title).toBe(`${de["setup.landing"]} — ${t("app.title")}`);
    expect(screen.getByText(de["setup.welcome.quote"])).toBeTruthy();
    expect(screen.getByText(de["setup.welcome.quoteSource"])).toBeTruthy();
    expect(screen.getByText(de["setup.welcome.trust1.label"])).toBeTruthy();
    expect(screen.getByText(de["setup.welcome.trust2.label"])).toBeTruthy();
    expect(screen.getByText(de["setup.welcome.trust3.label"])).toBeTruthy();
    expect(screen.getByText(de["setup.provisioning.footer.engine"])).toBeTruthy();
  });
});

describe("the landing — every door honest about what is not built yet", () => {
  it("the hero's three actions stay disabled with the drafted note", async () => {
    renderLanding();
    await screen.findByRole("heading", { level: 1, name: "Dead Signal" });

    for (const button of [writeButton(), loreButton(), storyboardButton()]) {
      expect(button.hasAttribute("disabled")).toBe(true);
      const noteId = button.getAttribute("aria-describedby");
      expect(noteId).not.toBeNull();
      expect(document.getElementById(noteId as string)?.textContent).toBe(
        de["setup.welcome.comingSoon"],
      );
    }
  });

  it("the three workrooms are coming-soon cards, not controls", async () => {
    renderLanding();
    await screen.findByRole("heading", { level: 1, name: "Dead Signal" });

    expect(screen.getByText(de["setup.landing.rooms.title"])).toBeTruthy();
    for (const key of ["setup.landing.room1.title", "setup.landing.room2.title", "setup.landing.room3.title"] as const) {
      expect(screen.getByText(de[key])).toBeTruthy();
    }
    expect(screen.getAllByText(de["setup.landing.rooms.soon"])).toHaveLength(3);
    // Static cards: no button, no link — nothing pretends to be a door.
    const rooms = screen.getByText(de["setup.landing.rooms.title"]).closest("section") as HTMLElement;
    expect(rooms.querySelectorAll("button, a")).toHaveLength(0);
    expect(within(rooms).getAllByText(de["setup.welcome.comingSoon"])).toHaveLength(3);
  });

  it("the new-work doors stay disabled; the demo list marks the active template", async () => {
    renderLanding();
    await screen.findByRole("heading", { level: 1, name: "Dead Signal" });

    const startButton = screen.getByRole("button", { name: de["setup.landing.new.workCta"] });
    const catalogButton = screen.getByRole("button", { name: de["setup.landing.new.catalog"] });
    expect(startButton.hasAttribute("disabled")).toBe(true);
    expect(catalogButton.hasAttribute("disabled")).toBe(true);
    expect(screen.getAllByText(de["setup.welcome.comingSoon"]).length).toBeGreaterThanOrEqual(2);

    // The three curated templates, listed but not clickable; the one the
    // shelf holds wears the active mark, the others their manifest meta.
    const activeMarks = screen.getAllByText(de["setup.landing.new.demoActive"]);
    expect(activeMarks).toHaveLength(1);
    const activeRow = activeMarks[0].closest("li") as HTMLElement;
    expect(within(activeRow).getByText("Dead Signal")).toBeTruthy();
    const list = activeRow.closest("ul") as HTMLElement;
    for (const demo of demos) {
      expect(within(list).getByText(demo.title)).toBeTruthy();
    }
    expect(list.querySelectorAll("button, a")).toHaveLength(0);
    expect(
      screen.getByText(t("setup.welcome.demoMeta", { genre: "Fantasy", count: 4 })),
    ).toBeTruthy();
  });
});

describe("the landing — the post-setup switcher writes the row", () => {
  it("switching to French PATCHes the settings row and speaks French", async () => {
    renderLanding();
    await screen.findByRole("heading", { level: 1, name: "Dead Signal" });

    const frRadio = screen.getByRole("radio", { name: catalogs.fr["locale.name"] });
    fireEvent.click(frRadio);

    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "fr" } }),
    );
    const fr = catalogs.fr;
    expect(await screen.findByText(fr["setup.landing.eyebrow"])).toBeTruthy();
    // The row is the record after setup: the refetch adopts the written
    // choice, and no pre-setup mirror is left behind.
    await waitFor(() => expect(api.GET.mock.calls.filter(([p]) => p === "/api/settings").length).toBeGreaterThanOrEqual(2));
    expect(localStorage.getItem("narrare.locale.preSetup")).toBeNull();
    expect(screen.getByRole("radio", { name: fr["locale.name"] }).getAttribute("aria-checked")).toBe("true");
  });

  it("the switcher keeps the radio keyboard contract", async () => {
    renderLanding();
    await screen.findByRole("heading", { level: 1, name: "Dead Signal" });

    const deRadio = screen.getByRole("radio", { name: catalogs.de["locale.name"] });
    deRadio.focus();
    fireEvent.keyDown(deRadio, { key: "ArrowRight" });

    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } }),
    );
    expect(await screen.findByText(catalogs.en["setup.landing.eyebrow"])).toBeTruthy();
    expect(screen.getByRole("radio", { name: catalogs.en["locale.name"] }).getAttribute("aria-checked")).toBe("true");
  });

  it("a refused switch restores the prior language", async () => {
    api.PATCH.mockImplementation(async () => ({
      error: { detail: "refused" },
      response: new Response(null, { status: 500 }),
    }));
    renderLanding();
    await screen.findByRole("heading", { level: 1, name: "Dead Signal" });

    fireEvent.click(screen.getByRole("radio", { name: catalogs.fr["locale.name"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    // The refusal snaps back: the German eyebrow stands again.
    await waitFor(() => expect(screen.getByText(de["setup.landing.eyebrow"])).toBeTruthy());
    expect(screen.getByRole("radio", { name: catalogs.de["locale.name"] }).getAttribute("aria-checked")).toBe("true");
  });
});

describe("the landing — a kept pre-setup mirror keeps speaking", () => {
  it("mirror present, row silent: the mirrored language speaks, read-only", async () => {
    // The browser speaks German; the kept mirror says French. The refused
    // seam left the row silent, so the preserved choice must keep speaking.
    vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
    rowLocale = null;
    localStorage.setItem("narrare.locale.preSetup", "fr");
    renderLanding();

    const fr = catalogs.fr;
    expect(await screen.findByText(fr["setup.landing.eyebrow"])).toBeTruthy();
    expect(
      screen.getByRole("radio", { name: fr["locale.name"] }).getAttribute("aria-checked"),
    ).toBe("true");
    // Read-only adoption: no write goes out, and the mirror stands untouched
    // until a switcher touch spends it.
    expect(api.PATCH).not.toHaveBeenCalled();
    expect(localStorage.getItem("narrare.locale.preSetup")).toBe("fr");
  });

  it("mirror absent, row silent: the browser's language stands unchanged", async () => {
    vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
    rowLocale = null;
    renderLanding();

    // No mirror to adopt: the boot's browser fallback speaks, nothing invented.
    expect(await screen.findByText(de["setup.landing.eyebrow"])).toBeTruthy();
    expect(api.PATCH).not.toHaveBeenCalled();
    expect(localStorage.getItem("narrare.locale.preSetup")).toBeNull();
  });

  it("a switcher touch spends the kept mirror and the row becomes the record", async () => {
    rowLocale = null;
    localStorage.setItem("narrare.locale.preSetup", "fr");
    renderLanding();

    expect(await screen.findByText(catalogs.fr["setup.landing.eyebrow"])).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: catalogs.de["locale.name"] }));

    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "de" } }),
    );
    expect(await screen.findByText(de["setup.landing.eyebrow"])).toBeTruthy();
    expect(localStorage.getItem("narrare.locale.preSetup")).toBeNull();
  });
});

describe("the landing — the shelf's failures surface, never a dressed-up shelf", () => {
  it("an empty shelf is a broken invariant, named as an error", async () => {
    novelsAnswer = async () => ({ data: [], response: ok() });
    renderLanding();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("shelf");
    expect(screen.queryByRole("heading", { level: 1, name: "Dead Signal" })).toBeNull();
  });

  it("an unreachable novels endpoint surfaces the root error", async () => {
    novelsAnswer = async () => ({ data: undefined, response: new Response(null, { status: 503 }) });
    renderLanding();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("503");
    expect(screen.queryByRole("heading", { level: 1, name: "Dead Signal" })).toBeNull();
  });

  it("while the shelf is in flight the page stays quiet", async () => {
    let resolveNovels!: (answer: { data: unknown; response: Response }) => void;
    novelsAnswer = () =>
      new Promise<{ data: unknown; response: Response }>((resolve) => {
        resolveNovels = resolve;
      });
    renderLanding();

    // The gate opened (status complete), but neither the shelf nor an error
    // is on screen while the one fact is outstanding.
    await waitFor(() => expect(api.GET).toHaveBeenCalledWith("/api/writing/novels"));
    expect(screen.queryByRole("heading", { level: 1, name: "Dead Signal" })).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();

    resolveNovels({ data: [NOVEL_ROW], response: ok() });
    expect(await screen.findByRole("heading", { level: 1, name: "Dead Signal" })).toBeTruthy();
  });
});
