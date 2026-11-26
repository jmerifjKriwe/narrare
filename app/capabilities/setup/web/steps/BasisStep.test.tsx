// @vitest-environment jsdom
/**
 * The wizard's first step, driven through the real router over the real root
 * route (the WelcomePage.test.tsx pattern): the answers ride search params,
 * so every assertion about state is an assertion about the address a refresh
 * would land on. Only the API client is mocked at its module boundary, and
 * the mock keeps the backend's pre-setup contract: the settings row does not
 * exist yet, so `PATCH /api/settings` refuses with 409 and the switcher's
 * mirror must hold the choice anyway.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
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

import { client } from "@shell/lib/api/client";
import { demos } from "@shell/lib/generated/demos";
import { t } from "@shell/lib/i18n";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

import { readPreSetupLocale, storePreSetupLocale } from "@shell/lib/preSetupLocale";
import { de, en } from "@shell/lib/test/catalogs";
import { routes } from "../routes";
import { DEFAULT_TARGET_WORDS, GENRE_CAP } from "../wizardState";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

function scriptApi() {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: null, theme: null }, response: ok() };
    }
    if (path === "/api/setup/status") {
      return { data: { complete: false }, response: ok() };
    }
    throw new Error(`unexpected request: ${path}`);
  });
  api.PATCH.mockImplementation(async (path: string) => {
    if (path !== "/api/settings") throw new Error(`unexpected request: ${path}`);
    // The row does not exist before setup: the structural refusal.
    return { error: { detail: "setup required" }, response: new Response(null, { status: 409 }) };
  });
}

function renderBasis(entry = "/setup/basis") {
  const router = createRouter({
    routeTree: rootRoute.addChildren([...routes]),
    history: createMemoryHistory({ initialEntries: [entry] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

/** The step's controls, named by the German catalog the mirror adopts. */
const titleField = () =>
  screen.getByRole("textbox", { name: de["setup.basis.titleLabel"] }) as HTMLInputElement;
const continueButton = () => screen.getByRole("button", { name: de["setup.basis.continue"] });
const wordsField = () =>
  screen.getByRole("spinbutton", { name: de["setup.basis.wordsLabel"] }) as HTMLInputElement;

/** The address as the wizard's seam reads it: the router types unvalidated
 *  search as `{}`, the answers are the record the parse defends against. */
function address(router: ReturnType<typeof renderBasis>): Record<string, unknown> {
  return router.state.location.search as Record<string, unknown>;
}

beforeEach(() => {
  scriptApi();
  localStorage.clear();
  // The German visitor: the mirror is the pre-setup record, the row holds
  // nothing yet — the page adopts it before paint, the welcome's contract.
  storePreSetupLocale("de");
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  applyLocale(null);
  localStorage.clear();
});

describe("the basis step — the blank path", () => {
  it("renders the draft's two ways, the stepper and the tab title", async () => {
    renderBasis();

    expect(await screen.findByRole("heading", { level: 1, name: de["setup.basis.heroTitle"] }))
      .toBeTruthy();
    expect(screen.getByText(de["setup.basis.optionA.title"])).toBeTruthy();
    expect(screen.getByText(de["setup.basis.optionB.title"])).toBeTruthy();
    expect(document.title).toBe(`${de["setup.basis"]} — ${t("app.title")}`);

    // The stepper: step one active, the other three named and waiting.
    const stepper = screen.getByRole("navigation", { name: de["setup.wizard.progress"] });
    for (const key of ["setup.wizard.step1", "setup.wizard.step2", "setup.wizard.step3", "setup.wizard.step4"] as const) {
      expect(within(stepper).getByText(de[key])).toBeTruthy();
    }
    expect(within(stepper).getByText(de["setup.wizard.step1"]).closest("[aria-current]")?.getAttribute("aria-current")).toBe("step");

    // The footer: cancel leads to the shelf, continue waits for the title.
    const cancel = screen.getByRole("link", { name: de["setup.basis.cancel"] });
    expect(cancel.getAttribute("href")).toBe("/");
    expect(continueButton().hasAttribute("disabled")).toBe(true);
  });

  it("syncs the title onto the live cover and into the address", async () => {
    const router = renderBasis();
    await screen.findByRole("heading", { level: 1 });

    // Untitled: the cover carries the honest placeholder and no author yet.
    expect(screen.getByText(de["setup.basis.coverUntitled"])).toBeTruthy();
    expect(screen.getByText(t("cover.anonymous"))).toBeTruthy();

    fireEvent.change(titleField(), { target: { value: "Die Winterchronik von Station Sieben" } });
    await waitFor(() => expect(screen.getByText("Die Winterchronik von Station Sieben")).toBeTruthy());
    expect(router.state.location.search).toMatchObject({ title: "Die Winterchronik von Station Sieben" });

    // Clearing returns the placeholder — and drops the param, not blanks it.
    fireEvent.change(titleField(), { target: { value: "" } });
    await waitFor(() => expect(screen.getByText(de["setup.basis.coverUntitled"])).toBeTruthy());
    expect(address(router).title).toBeUndefined();
  });

  it("keeps whitespace while typing — the address round trip never eats the field", async () => {
    const router = renderBasis();
    await screen.findByRole("heading", { level: 1 });

    // A lone space stays in the field even though the address carries no
    // title: the draft holds the keystroke the serialization would drop.
    fireEvent.change(titleField(), { target: { value: " " } });
    expect(titleField().value).toBe(" ");
    expect(address(router).title).toBeUndefined();

    // Whitespace is still not a title: panel 1's validation stands.
    expect(screen.getByText(de["setup.basis.titleError"])).toBeTruthy();
    expect(continueButton().hasAttribute("disabled")).toBe(true);

    // Leading spaces survive into real text, on screen and in the address.
    fireEvent.change(titleField(), { target: { value: "  Die Winterchronik" } });
    await waitFor(() => expect(address(router).title).toBe("  Die Winterchronik"));
    expect(titleField().value).toBe("  Die Winterchronik");
    expect(continueButton().hasAttribute("disabled")).toBe(false);

    // Blur snaps the field to the value the address carries — a whitespace-
    // only entry falls back to empty, never a title the POST would not send.
    fireEvent.change(titleField(), { target: { value: "   " } });
    fireEvent.blur(titleField());
    await waitFor(() => expect(titleField().value).toBe(""));
    expect(address(router).title).toBeUndefined();
    expect(screen.getByText(de["setup.basis.titleError"])).toBeTruthy();
    expect(continueButton().hasAttribute("disabled")).toBe(true);
  });

  it("validates deterministically: the error line and the locked continue until a title stands", async () => {
    renderBasis();
    await screen.findByRole("heading", { level: 1 });

    // Panel 1 of the states reference: the missing title is named at once.
    expect(screen.getByText(de["setup.basis.titleError"])).toBeTruthy();
    expect(continueButton().hasAttribute("disabled")).toBe(true);
    expect(screen.getByText(t("setup.basis.status.incomplete", { step: 1, total: 4 }))).toBeTruthy();
    expect(titleField().getAttribute("aria-invalid")).toBe("true");

    fireEvent.change(titleField(), { target: { value: "Ein Titel" } });
    await waitFor(() => expect(continueButton().hasAttribute("disabled")).toBe(false));
    expect(screen.queryByText(de["setup.basis.titleError"])).toBeNull();
    expect(screen.getByText(t("setup.basis.status.configured", { step: 1, total: 4 }))).toBeTruthy();

    // Whitespace is not a title: the lock returns.
    fireEvent.change(titleField(), { target: { value: "   " } });
    await waitFor(() => expect(continueButton().hasAttribute("disabled")).toBe(true));
    expect(screen.getByText(de["setup.basis.titleError"])).toBeTruthy();
  });

  it("toggles the genre pills and joins them into the one address string", async () => {
    const router = renderBasis();
    await screen.findByRole("heading", { level: 1 });

    const scifi = screen.getByRole("button", { name: de["setup.basis.genre.scifi"] });
    const literary = screen.getByRole("button", { name: de["setup.basis.genre.literary"] });
    expect(scifi.getAttribute("aria-pressed")).toBe("false");

    fireEvent.click(scifi);
    await waitFor(() => expect(scifi.getAttribute("aria-pressed")).toBe("true"));
    fireEvent.click(literary);
    await waitFor(() =>
      expect(address(router).genres).toBe(
        "Science Fiction & Speculative,Literarische Belletristik",
      ),
    );

    // The cover takes the first chosen genre's channel (the BookCover root,
    // not the demo mini-covers' motifs, which always wear their own).
    expect(document.querySelector("[data-variant][data-channel='scifi']")).toBeTruthy();

    fireEvent.click(scifi);
    await waitFor(() => expect(address(router).genres).toBe("Literarische Belletristik"));
  });

  it("disables the pill that would overflow the 80-char cap, with the honest note", async () => {
    renderBasis();
    await screen.findByRole("heading", { level: 1 });

    const scifi = screen.getByRole("button", { name: de["setup.basis.genre.scifi"] });
    const literary = screen.getByRole("button", { name: de["setup.basis.genre.literary"] });
    const lowFantasy = screen.getByRole("button", { name: de["setup.basis.genre.lowfantasy"] });

    fireEvent.click(scifi);
    fireEvent.click(literary);
    // 29 + 25 + 2 = 56 fits; the 33-char Low Fantasy would run to 91.
    await waitFor(() => expect(lowFantasy.hasAttribute("disabled")).toBe(true));
    expect(screen.getByText(t("setup.basis.genreCapNote", { cap: GENRE_CAP }))).toBeTruthy();

    // Removing one selection reopens the door; the note goes with it.
    fireEvent.click(literary);
    await waitFor(() => expect(lowFantasy.hasAttribute("disabled")).toBe(false));
    expect(screen.queryByText(t("setup.basis.genreCapNote", { cap: GENRE_CAP }))).toBeNull();
  });

  it("keeps the draft's word target, gauge band and Normseiten honest", async () => {
    const router = renderBasis();
    await screen.findByRole("heading", { level: 1 });

    expect(wordsField().value).toBe(String(DEFAULT_TARGET_WORDS));
    expect(screen.getByText(de["setup.basis.band.novel"])).toBeTruthy();
    expect(screen.getByText(de["setup.basis.range.novel"])).toBeTruthy();
    expect(screen.getByText(t("setup.basis.normseiten", { count: 240 }))).toBeTruthy();

    fireEvent.change(wordsField(), { target: { value: "120000" } });
    await waitFor(() => expect(screen.getByText(de["setup.basis.band.epic"])).toBeTruthy());
    expect(screen.getByText(de["setup.basis.range.epic"])).toBeTruthy();
    expect(address(router).words).toBe(120000);

    // A cleared field snaps back to the value that would actually be sent —
    // the last valid target, never a number the POST would not carry.
    fireEvent.change(wordsField(), { target: { value: "" } });
    fireEvent.blur(wordsField());
    await waitFor(() => expect(wordsField().value).toBe("120000"));
    expect(address(router).words).toBe(120000);
  });

  it("carries the accumulated answers into step two", async () => {
    const router = renderBasis();
    await screen.findByRole("heading", { level: 1 });

    fireEvent.change(titleField(), { target: { value: "Die Winterchronik" } });
    fireEvent.click(screen.getByRole("button", { name: de["setup.basis.genre.mystery"] }));
    fireEvent.change(wordsField(), { target: { value: "80000" } });
    await waitFor(() => expect(continueButton().hasAttribute("disabled")).toBe(false));

    fireEvent.click(continueButton());
    await waitFor(() => expect(router.state.location.pathname).toBe("/setup/structure"));
    expect(router.state.location.search).toMatchObject({
      title: "Die Winterchronik",
      genres: "Mystery & Noir",
      words: 80000,
    });
  });

  it("restores every answer from the address — the refresh shape", async () => {
    const search = new URLSearchParams({
      title: "Die Winterchronik",
      genres: "Mystery & Noir,Historischer Roman",
      words: "80000",
    });
    renderBasis(`/setup/basis?${search.toString()}`);
    await screen.findByRole("heading", { level: 1 });

    expect(titleField().value).toBe("Die Winterchronik");
    expect(wordsField().value).toBe("80000");
    expect(screen.getByRole("button", { name: de["setup.basis.genre.mystery"] }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: de["setup.basis.genre.historical"] }).getAttribute("aria-pressed")).toBe("true");
    expect(continueButton().hasAttribute("disabled")).toBe(false);
  });
});

describe("the basis step — the demo path", () => {
  it("preselects from ?demo= and binds title and genre with the lock note", async () => {
    renderBasis("/setup/basis?demo=dead-signal");
    await screen.findByRole("heading", { level: 1 });

    const demo = demos[0];
    // Panel 2: the fields are locked and wear the archive's identity.
    const boundTitle = screen.getByRole("textbox", {
      name: de["setup.basis.boundTitle"],
    }) as HTMLInputElement;
    expect(boundTitle.hasAttribute("disabled")).toBe(true);
    expect(boundTitle.value).toBe(demo.title);
    const boundGenre = screen.getByRole("textbox", {
      name: de["setup.basis.boundGenre"],
    }) as HTMLInputElement;
    expect(boundGenre.hasAttribute("disabled")).toBe(true);
    expect(boundGenre.value).toBe(demo.genre);
    expect(screen.getByText(de["setup.basis.lockNote"])).toBeTruthy();

    // The word target belongs to the blank path only.
    expect(screen.queryByRole("spinbutton")).toBeNull();

    // The banner names the chosen basis; continue stands without a title.
    expect(screen.getByText(t("setup.basis.banner.title", { title: demo.title }))).toBeTruthy();
    expect(screen.getByText(t("setup.basis.banner.meta", { genre: demo.genre, count: demo.chapters }))).toBeTruthy();
    expect(continueButton().hasAttribute("disabled")).toBe(false);
    expect(screen.getByText(t("setup.basis.status.configured", { step: 1, total: 4 }))).toBeTruthy();

    // The selected card wears the badge and the active button.
    const card = document.getElementById(`demo-${demo.slug}`) as HTMLElement;
    expect(within(card).getByText(de["setup.basis.demoSelected"])).toBeTruthy();
    expect(within(card).getByRole("button", { name: de["setup.basis.demoActive"] })).toBeTruthy();
    // The cover preview carries the archive's title.
    expect(screen.getByText(demo.title, { selector: "span" })).toBeTruthy();
  });

  it("binds on selection and releases on the active button — the address follows", async () => {
    const router = renderBasis();
    await screen.findByRole("heading", { level: 1 });

    const card = document.getElementById(`demo-${demos[1].slug}`) as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { name: de["setup.basis.demoSelect"] }));
    await waitFor(() => expect(address(router).demo).toBe(demos[1].slug));
    expect(
      (screen.getByRole("textbox", { name: de["setup.basis.boundTitle"] }) as HTMLInputElement).value,
    ).toBe(demos[1].title);
    expect(screen.getByText(de["setup.basis.lockNote"])).toBeTruthy();

    fireEvent.click(within(card).getByRole("button", { name: de["setup.basis.demoActive"] }));
    await waitFor(() => expect(address(router).demo).toBeUndefined());
    expect(titleField().hasAttribute("disabled")).toBe(false);
    expect(screen.queryByText(de["setup.basis.lockNote"])).toBeNull();
    expect(continueButton().hasAttribute("disabled")).toBe(true);
  });

  it("the tabula-rasa button clears the binding and hands focus to the title", async () => {
    renderBasis("/setup/basis?demo=im-stillen-wald");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByRole("textbox", { name: de["setup.basis.boundTitle"] })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: de["setup.basis.optionA.cta"] }));
    await waitFor(() => expect(titleField().hasAttribute("disabled")).toBe(false));
    expect(document.activeElement).toBe(titleField());
    expect(screen.queryByText(de["setup.basis.lockNote"])).toBeNull();
  });

  it("the banner's details link anchors to the selected card", async () => {
    renderBasis("/setup/basis?demo=echoes-of-the-thornwall");
    await screen.findByRole("heading", { level: 1 });

    const details = screen.getByRole("link", { name: de["setup.basis.banner.details"] });
    expect(details.getAttribute("href")).toBe("#demo-echoes-of-the-thornwall");
  });

  it("carries the three real demos — title, genre, blurb, chapters, and nothing invented", async () => {
    renderBasis();
    await screen.findByRole("heading", { level: 1 });

    expect(demos).toHaveLength(3);
    for (const demo of demos) {
      const card = document.getElementById(`demo-${demo.slug}`) as HTMLElement;
      expect(card).toBeTruthy();
      // The metadata title and the mini cover's title both stand; the genre
      // rides the mini cover's foot and the metadata chip.
      expect(within(card).getAllByText(demo.title).length).toBeGreaterThanOrEqual(2);
      expect(within(card).getAllByText(demo.genre)).toHaveLength(2);
      expect(within(card).getByText(t("setup.basis.demoChaptersWritten", { count: demo.chapters }))).toBeTruthy();
      expect(within(card).getByText(`„${demo.blurb}“`)).toBeTruthy();
      expect(within(card).getByRole("button", { name: de["setup.basis.demoSelect"] })).toBeTruthy();
    }
    // No stat chips, no entity counts — the archive's facts only.
    expect(screen.queryByText(/Entitäten/)).toBeNull();
    expect(screen.queryByText(/8 Entitäten|16 Entitäten|6 Entitäten|18 Entitäten/)).toBeNull();
  });
});

describe("the step's header", () => {
  it("keeps the draft's DE|EN|FR switcher working before setup", async () => {
    renderBasis();
    await screen.findByRole("heading", { level: 1 });

    const group = screen.getByRole("radiogroup", { name: de["shell.language"] });
    const radios = within(group).getAllByRole("radio");
    expect(radios.map((radio) => radio.textContent)).toEqual(["DE", "EN", "FR"]);
    expect(radios[0].getAttribute("aria-checked")).toBe("true");

    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await screen.findByRole("heading", { level: 1, name: en["setup.basis.heroTitle"] });
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } });
    // The structural 409 settled: the mirror holds the choice.
    await waitFor(() => expect(readPreSetupLocale()).toBe("en"));
  });

  it("keeps the help control honestly disabled until the handbook exists", async () => {
    renderBasis();
    await screen.findByRole("heading", { level: 1 });

    const help = screen.getByRole("button", { name: de["setup.basis.help"] });
    expect(help.hasAttribute("disabled")).toBe(true);
  });
});