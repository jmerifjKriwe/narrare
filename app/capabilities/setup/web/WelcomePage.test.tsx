// @vitest-environment jsdom
/**
 * The welcome screen's wiring, driven through the real router over the real
 * root route (the routes.test.tsx pattern): the `/` gate opens onto the
 * welcome while setup is incomplete, and the page's own doors, demos and
 * switcher run unmocked. Only the API client is mocked at its module
 * boundary — and the mock keeps the backend's own contract: before setup
 * the user row does not exist, so `PATCH /api/settings` refuses with 409
 * "setup required" (settings/service.py). The switcher must still work in
 * that state; the pre-setup mirror is what makes a refresh keep the choice.
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
import { catalogs, locales } from "@shell/lib/generated/catalogs";
import { demos } from "@shell/lib/generated/demos";
import { t } from "@shell/lib/i18n";
import { activeLocale, applyLocale, chosenLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

import { readPreSetupLocale, storePreSetupLocale } from "./preSetupLocale";
import { routes } from "./routes";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The mock instance's state: setup creates the user row, and only then can
 *  the settings write land — the backend's own sequence. */
let setUp: boolean;
let storedLocale: string | null;

function scriptApi() {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: storedLocale, theme: null }, response: ok() };
    }
    if (path === "/api/setup/status") {
      return { data: { complete: setUp }, response: ok() };
    }
    throw new Error(`unexpected request: ${path}`);
  });
  api.PATCH.mockImplementation(async (path: string, init?: { body?: { locale?: string | null } }) => {
    if (path !== "/api/settings") throw new Error(`unexpected request: ${path}`);
    if (!setUp) {
      // The row does not exist yet: the write refuses, the row stays empty.
      return { error: { detail: "setup required" }, response: new Response(null, { status: 409 }) };
    }
    storedLocale = init?.body?.locale ?? null;
    return { data: { locale: storedLocale, theme: null }, response: ok() };
  });
}

/** The fresh-load shape: the gate asks the status, the welcome answers. */
function renderWelcome() {
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

beforeEach(() => {
  setUp = false;
  storedLocale = null;
  scriptApi();
  // The German visitor who chose their language on an earlier visit: the
  // mirror is the pre-setup record, the row holds nothing yet.
  localStorage.clear();
  storePreSetupLocale("de");
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  // The locale is global state; the test must not leak it.
  applyLocale(null);
  localStorage.clear();
});

describe("the welcome screen", () => {
  it("adopts the mirrored language, greets du-tone, and names the tab", async () => {
    renderWelcome();

    // The shell adopted the row's null; the page's mirror speaks before
    // paint. The expectation reads the German catalog itself — t() at call
    // time would still speak the browser's language, the pre-adoption state.
    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading.textContent).toBe(catalogs.de["setup.welcome.heroTitle"]);
    expect(screen.getByText(catalogs.de["setup.welcome.heroBody"])).toBeTruthy();
    // The du-tone is the copy's own: "deiner", not "Ihrer".
    expect(screen.getByText(/zu deiner eigenen Erzählarchitektur/)).toBeTruthy();
    expect(document.title).toBe(`${catalogs.de["setup.welcome"]} — ${t("app.title")}`);
    expect(screen.getByRole("radio", { name: "Deutsch" }).getAttribute("aria-checked")).toBe("true");
  });

  it("offers the three entries — wizard, demos, import", async () => {
    renderWelcome();
    await screen.findByRole("heading", { level: 1 });

    // The wizard's door, and the demo card's lead CTA after the first demo.
    const wizard = screen.getByRole("link", { name: catalogs.de["setup.welcome.card1.cta"] });
    expect(wizard.getAttribute("href")).toBe("/setup/basis");
    const lead = screen.getByRole("link", { name: catalogs.de["setup.welcome.card2.cta"] });
    expect(lead.getAttribute("href")).toBe(`/setup/basis?demo=${demos[0].slug}`);

    // The import entry is honestly disabled, and says why.
    const importButton = screen.getByRole("button", { name: catalogs.de["setup.welcome.card3.cta"] });
    expect(importButton.hasAttribute("disabled")).toBe(true);
    expect(screen.getByText(catalogs.de["setup.welcome.comingSoon"])).toBeTruthy();
  });

  it("carries the three real demos — title, genre, chapters, and their doors", async () => {
    renderWelcome();
    await screen.findByRole("heading", { level: 1 });

    expect(demos).toHaveLength(3);
    for (const demo of demos) {
      expect(screen.getByText(`»${demo.title}«`)).toBeTruthy();
      expect(
        screen.getByText(t("setup.welcome.demoMeta", { genre: demo.genre, count: demo.chapters })),
      ).toBeTruthy();
      // The row itself is the door: the wizard opens with the world chosen.
      const row = screen.getByRole("link", { name: new RegExp(demo.title) });
      expect(row.getAttribute("href")).toBe(`/setup/basis?demo=${demo.slug}`);
      // Title/genre/chapters only — the blurb stays in the archive.
      expect(screen.queryByText(demo.blurb)).toBeNull();
    }
  });

  it("keeps the draft's full-bleed pinned composition and selectable copy", async () => {
    renderWelcome();
    await screen.findByRole("heading", { level: 1 });

    // The page root is the draft's `main`: full breadth, pinned ends, and
    // no selection lock — the copy is meant to be read and copied.
    const root = document.querySelector("#main > div") as HTMLElement;
    expect(root.className).toContain("min-h-screen");
    expect(root.className).toContain("justify-between");
    expect(root.className).toContain("w-full");
    expect(root.className).toContain("selection:bg-secondary-container");
    expect(root.className).not.toContain("max-w-6xl");
    expect(root.className).not.toContain("select-none");
    // Header at the top, footer at the bottom, the grid spanning between.
    expect(root.firstElementChild?.tagName).toBe("HEADER");
    expect(root.lastElementChild?.tagName).toBe("FOOTER");
    const grid = root.children[2] as HTMLElement;
    expect(grid.className).toContain("grid");
    expect(grid.className).toContain("w-full");
    expect(grid.className).not.toContain("max-w-");
  });
});

describe("the language switcher", () => {
  it("draws the draft's DE|EN|FR order as a radio group with one tab stop", async () => {
    renderWelcome();
    await screen.findByRole("heading", { level: 1 });

    // The generated order is the compiler's (en first); the design's is not.
    expect(locales[0]).toBe("en");
    const group = screen.getByRole("radiogroup", {
      name: catalogs.de["setup.welcome.language"],
    });
    const radios = within(group).getAllByRole("radio");
    expect(radios.map((radio) => radio.textContent)).toEqual(["DE", "EN", "FR"]);
    expect(radios.map((radio) => radio.getAttribute("aria-label"))).toEqual([
      "Deutsch",
      "English",
      "Français",
    ]);
    expect(radios.map((radio) => radio.getAttribute("aria-checked"))).toEqual([
      "true",
      "false",
      "false",
    ]);
    expect(radios.map((radio) => radio.tabIndex)).toEqual([0, -1, -1]);
  });

  it("cycles with the arrows, wrapping, and focus follows the choice", async () => {
    renderWelcome();
    await screen.findByRole("heading", { level: 1 });

    const radio = (name: string) => screen.getByRole("radio", { name });
    radio("Deutsch").focus();
    fireEvent.keyDown(radio("Deutsch"), { key: "ArrowRight" });
    await waitFor(() => expect(radio("English").getAttribute("aria-checked")).toBe("true"));
    expect(document.activeElement).toBe(radio("English"));

    // Wrap at the left end: DE's left neighbour is FR, the draft's last.
    fireEvent.keyDown(radio("Deutsch"), { key: "ArrowLeft" });
    await waitFor(() => expect(radio("Français").getAttribute("aria-checked")).toBe("true"));
    expect(document.activeElement).toBe(radio("Français"));
    expect(readPreSetupLocale()).toBe("fr");

    // Home returns to the draft's lead; the tab stop travels with it.
    fireEvent.keyDown(radio("Français"), { key: "Home" });
    await waitFor(() => expect(radio("Deutsch").getAttribute("aria-checked")).toBe("true"));
    expect(radio("Deutsch").tabIndex).toBe(0);
    expect(radio("English").tabIndex).toBe(-1);
  });

  it("works before setup: applies, attempts the write, keeps the choice on the structural 409", async () => {
    renderWelcome();
    await screen.findByRole("heading", { level: 1 });

    fireEvent.click(screen.getByRole("radio", { name: "English" }));

    // Applied at once, and the write goes through the settings API.
    await screen.findByRole("heading", { level: 1, name: "Step in. Your unwritten work awaits." });
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } });
    // The 409 settled and the choice stands — no snap-back, the mirror holds.
    await waitFor(() => expect(readPreSetupLocale()).toBe("en"));
    expect(activeLocale()).toBe("en");
    expect(chosenLocale()).toBe("en");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Step in. Your unwritten work awaits.",
    );
    expect(screen.getByRole("radio", { name: "English" }).getAttribute("aria-checked")).toBe("true");
    // The row could not take the write, so no settings refetch is owed.
    expect(api.GET.mock.calls.filter(([path]) => path === "/api/settings")).toHaveLength(1);
  });

  it("a refresh keeps the mirrored choice without another write", async () => {
    renderWelcome();
    await screen.findByRole("heading", { level: 1 });
    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await waitFor(() => expect(readPreSetupLocale()).toBe("en"));

    // The browser-refresh shape: a fresh mount, the same instance state.
    cleanup();
    renderWelcome();
    expect(await screen.findByRole("heading", { level: 1, name: "Step in. Your unwritten work awaits." }))
      .toBeTruthy();
    expect(api.PATCH).toHaveBeenCalledTimes(1); // the first visit's write only
  });

  it("a landed write clears the mirror and refreshes the cached row", async () => {
    renderWelcome();
    await screen.findByRole("heading", { level: 1 });

    // Setup completes while the page is open (another tab, the wizard's own
    // finish): the row exists now, so the write lands in it.
    setUp = true;
    fireEvent.click(screen.getByRole("radio", { name: "English" }));

    await screen.findByRole("heading", { level: 1, name: "Step in. Your unwritten work awaits." });
    await waitFor(() => expect(readPreSetupLocale()).toBeNull());
    expect(storedLocale).toBe("en");
    // The row changed, so the cached settings answer is asked again — and
    // the shell re-adopts the persisted locale, not a remembered one.
    await waitFor(() =>
      expect(api.GET.mock.calls.filter(([path]) => path === "/api/settings").length).toBeGreaterThanOrEqual(2),
    );
    expect(activeLocale()).toBe("en");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Step in. Your unwritten work awaits.",
    );
  });

  it("any other refusal restores the prior choice and its mirror", async () => {
    renderWelcome();
    await screen.findByRole("heading", { level: 1 });

    api.PATCH.mockResolvedValueOnce({
      error: { detail: "refused" },
      response: new Response(null, { status: 503 }),
    });
    fireEvent.click(screen.getByRole("radio", { name: "English" }));

    // The write did not happen, so neither the store nor the page pretends.
    await waitFor(() => expect(activeLocale()).toBe("de"));
    expect(chosenLocale()).toBe("de");
    expect(readPreSetupLocale()).toBe("de");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      catalogs.de["setup.welcome.heroTitle"],
    );
    expect(screen.getByRole("radio", { name: "Deutsch" }).getAttribute("aria-checked")).toBe("true");
  });

  it("speaks French tu-tone after the switch", async () => {
    renderWelcome();
    await screen.findByRole("heading", { level: 1 });

    fireEvent.click(screen.getByRole("radio", { name: "Français" }));

    await screen.findByRole("heading", { level: 1, name: "Entre. Ton œuvre non écrite t'attend." });
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "fr" } });
    expect(screen.getByText(/Façonne tes personnages/)).toBeTruthy();
    await waitFor(() => expect(readPreSetupLocale()).toBe("fr"));
  });
});
