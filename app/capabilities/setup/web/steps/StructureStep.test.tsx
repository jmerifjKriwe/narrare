// @vitest-environment jsdom
/**
 * The wizard's second step, driven through the real router over the real root
 * route (the BasisStep.test.tsx pattern): the answers ride search params, so
 * every assertion about state is an assertion about the address a refresh
 * would land on. Only the API client is mocked at its module boundary, and the
 * mock keeps the backend's pre-setup contract: the settings row does not exist
 * yet, so `PATCH /api/settings` refuses with 409 and the switcher's mirror must
 * hold the choice anyway.
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

import { storePreSetupLocale } from "@shell/lib/preSetupLocale";
import { routes } from "../routes";

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

function renderStructure(entry = "/setup/structure") {
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
const de = catalogs.de;
const continueButton = () => screen.getByRole("button", { name: de["setup.structure.continue"] });
const backButton = () => screen.getByRole("link", { name: de["setup.structure.back"] });
const typologyRadio = (key: "plotter" | "pantser" | "plantser") =>
  screen.getByRole("radio", { name: de[`setup.structure.typology.${key}.label`] });
const formRadio = (key: "threeAct" | "herosJourney" | "sevenPoint" | "fiveAct" | "saveTheCat") =>
  screen.getByRole("radio", { name: de[`setup.structure.form.${key}.label`] });

/** The address as the wizard's seam reads it. */
function address(router: ReturnType<typeof renderStructure>): Record<string, unknown> {
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

describe("the structure step — the draft's catalog", () => {
  it("renders the five forms with their meta lines, the three typologies and the tab title", async () => {
    renderStructure();

    expect(
      await screen.findByRole("heading", { level: 1, name: de["setup.structure.heroTitle"] }),
    ).toBeTruthy();
    expect(document.title).toBe(`${de["setup.structure"]} — ${t("app.title")}`);

    // The three typologies, by their drafted labels.
    for (const key of ["plotter", "pantser", "plantser"] as const) {
      expect(typologyRadio(key)).toBeTruthy();
    }

    // The five forms, by their drafted labels, in the draft's order.
    const formLabels = [
      de["setup.structure.form.threeAct.label"],
      de["setup.structure.form.herosJourney.label"],
      de["setup.structure.form.sevenPoint.label"],
      de["setup.structure.form.fiveAct.label"],
      de["setup.structure.form.saveTheCat.label"],
    ];
    for (const label of formLabels) {
      expect(screen.getByRole("radio", { name: label })).toBeTruthy();
    }

    // The four count meta lines the brief binds.
    expect(screen.getByText(de["setup.structure.form.herosJourney.meta"])).toBeTruthy();
    expect(screen.getByText(de["setup.structure.form.sevenPoint.meta"])).toBeTruthy();
    expect(screen.getByText(de["setup.structure.form.fiveAct.meta"])).toBeTruthy();
    expect(screen.getByText(de["setup.structure.form.saveTheCat.meta"])).toBeTruthy();

    // The paradigm badge counts the five.
    expect(screen.getByText(t("setup.structure.form.badge", { count: 5 }))).toBeTruthy();
  });

  it("speaks the du-tone in the rendered German intro", async () => {
    renderStructure();
    const body = await screen.findByText(de["setup.structure.heroBody"]);
    expect(body.textContent).toContain("deine");
  });

  it("marks step two active and step one done in the stepper", async () => {
    renderStructure();
    await screen.findByRole("heading", { level: 1 });

    const stepper = screen.getByRole("navigation", { name: de["setup.wizard.progress"] });
    for (const key of ["setup.wizard.step1", "setup.wizard.step2", "setup.wizard.step3", "setup.wizard.step4"] as const) {
      expect(within(stepper).getByText(de[key])).toBeTruthy();
    }
    expect(
      within(stepper).getByText(de["setup.wizard.step2"]).closest("[aria-current]")?.getAttribute("aria-current"),
    ).toBe("step");
    // Step one is done: it carries the check, not the active ring.
    expect(
      within(stepper).getByText(de["setup.wizard.step1"]).closest("[aria-current]"),
    ).toBeNull();
  });
});

describe("the structure step — the dead-signal condition", () => {
  it("shows the three-act hint and the plotter default badge only on the dead-signal basis", async () => {
    renderStructure("/setup/structure?demo=dead-signal");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.getByText(de["setup.structure.form.threeAct.hint"])).toBeTruthy();
    expect(screen.getByText(de["setup.structure.typology.plotter.badge"])).toBeTruthy();
  });

  it("stays neutral on the blank path — no dead-signal hint, no default badge", async () => {
    renderStructure();
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByText(de["setup.structure.form.threeAct.hint"])).toBeNull();
    expect(screen.queryByText(de["setup.structure.typology.plotter.badge"])).toBeNull();
  });

  it("stays neutral on another demo's basis", async () => {
    renderStructure(`/setup/structure?demo=${demos[1].slug}`);
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByText(de["setup.structure.form.threeAct.hint"])).toBeNull();
    expect(screen.queryByText(de["setup.structure.typology.plotter.badge"])).toBeNull();
  });
});

describe("the structure step — selection and the address", () => {
  it("keeps continue disabled until both a typology and a form are chosen", async () => {
    renderStructure();
    await screen.findByRole("heading", { level: 1 });

    // Neither chosen: locked, and no error text (the draft shows none).
    expect(continueButton().hasAttribute("disabled")).toBe(true);

    // Typology alone is not enough.
    fireEvent.click(typologyRadio("pantser"));
    await waitFor(() => expect(typologyRadio("pantser").getAttribute("aria-checked")).toBe("true"));
    expect(continueButton().hasAttribute("disabled")).toBe(true);

    // A form alone (fresh address) is not enough either.
    renderStructureAfterCleanup();
    await screen.findByRole("heading", { level: 1 });
    fireEvent.click(formRadio("herosJourney"));
    await waitFor(() => expect(formRadio("herosJourney").getAttribute("aria-checked")).toBe("true"));
    expect(continueButton().hasAttribute("disabled")).toBe(true);

    // Both together unlock the door.
    fireEvent.click(typologyRadio("plantser"));
    await waitFor(() => expect(continueButton().hasAttribute("disabled")).toBe(false));
  });

  it("persists the typology and the form into the address", async () => {
    const router = renderStructure();
    await screen.findByRole("heading", { level: 1 });

    fireEvent.click(typologyRadio("pantser"));
    fireEvent.click(formRadio("saveTheCat"));
    await waitFor(() => expect(address(router).typology).toBe("pantser"));
    expect(address(router).form).toBe("save-the-cat");

    // The selected form wears the active indicator.
    fireEvent.click(formRadio("threeAct"));
    await waitFor(() => expect(address(router).form).toBe("three-act"));
    expect(screen.getByText(de["setup.structure.form.active"])).toBeTruthy();
  });

  it("restores both selections from the address — the refresh shape", async () => {
    renderStructure("/setup/structure?typology=plantser&form=heros-journey");
    await screen.findByRole("heading", { level: 1 });

    expect(typologyRadio("plantser").getAttribute("aria-checked")).toBe("true");
    expect(formRadio("herosJourney").getAttribute("aria-checked")).toBe("true");
    expect(continueButton().hasAttribute("disabled")).toBe(false);
  });

  it("back to step one keeps the accumulated state", async () => {
    const router = renderStructure("/setup/structure?demo=dead-signal&title=Die%20Winterchronik");
    await screen.findByRole("heading", { level: 1 });

    fireEvent.click(typologyRadio("plotter"));
    fireEvent.click(formRadio("threeAct"));
    await waitFor(() => expect(continueButton().hasAttribute("disabled")).toBe(false));

    fireEvent.click(backButton());
    await waitFor(() => expect(router.state.location.pathname).toBe("/setup/basis"));
    expect(router.state.location.search).toMatchObject({
      demo: "dead-signal",
      title: "Die Winterchronik",
      typology: "plotter",
      form: "three-act",
    });
  });

  it("forward to step three carries the state", async () => {
    const router = renderStructure();
    await screen.findByRole("heading", { level: 1 });

    fireEvent.click(typologyRadio("pantser"));
    fireEvent.click(formRadio("sevenPoint"));
    await waitFor(() => expect(continueButton().hasAttribute("disabled")).toBe(false));

    fireEvent.click(continueButton());
    await waitFor(() => expect(router.state.location.pathname).toBe("/setup/ai-rules"));
    expect(router.state.location.search).toMatchObject({
      typology: "pantser",
      form: "seven-point",
    });
  });
});

describe("the structure step — the basis banner and the honest status", () => {
  it("names the chosen demo in the banner, with the causality chip", async () => {
    renderStructure("/setup/structure?demo=dead-signal");
    await screen.findByRole("heading", { level: 1 });

    const demo = demos[0];
    expect(screen.getByText(de["setup.structure.banner.label"])).toBeTruthy();
    // The draft names the basis twice: the strip and the preview's header.
    expect(
      screen.getAllByText(t("setup.structure.banner.demoTitle", { title: demo.title })),
    ).toHaveLength(2);
    expect(
      screen.getByText(t("setup.structure.banner.demoMeta", { genre: demo.genre, count: demo.chapters })),
    ).toBeTruthy();
    expect(screen.getByText(de["setup.structure.banner.note"])).toBeTruthy();
    expect(screen.getByText(de["setup.structure.banner.causality"])).toBeTruthy();
  });

  it("is honest and minimal on the blank path — no demo facts", async () => {
    renderStructure();
    await screen.findByRole("heading", { level: 1 });

    expect(screen.getByText(de["setup.structure.banner.label"])).toBeTruthy();
    expect(screen.getByText(de["setup.structure.banner.blank"])).toBeTruthy();
    expect(screen.getByText(de["setup.structure.banner.causality"])).toBeTruthy();
    // No demo title, no template note on the blank path.
    expect(screen.queryByText(t("setup.structure.banner.demoTitle", { title: demos[0].title }))).toBeNull();
    expect(screen.queryByText(de["setup.structure.banner.note"])).toBeNull();
  });

  it("carries the honest timeline status line and no entity counts anywhere", async () => {
    renderStructure("/setup/structure?demo=dead-signal");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.getByText(de["setup.structure.preview.timeline"])).toBeTruthy();
    // The corrected draft's promise: no entity/node counts on this step.
    expect(screen.queryByText(/Entitäten/)).toBeNull();
    expect(screen.queryByText(/8 Entitäten|16 Entitäten|6 Entitäten|18 Entitäten/)).toBeNull();
    expect(screen.queryByText(/Knoten/)).toBeNull();
  });
});

describe("the structure step's header", () => {
  it("keeps the draft's DE|EN|FR switcher working before setup", async () => {
    renderStructure();
    await screen.findByRole("heading", { level: 1 });

    const group = screen.getByRole("radiogroup", { name: de["shell.language"] });
    const radios = within(group).getAllByRole("radio");
    expect(radios.map((radio) => radio.textContent)).toEqual(["DE", "EN", "FR"]);
    expect(radios[0].getAttribute("aria-checked")).toBe("true");

    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await screen.findByRole("heading", { level: 1, name: catalogs.en["setup.structure.heroTitle"] });
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } });
  });
});

describe("the structure step — the live preview and the keyboard", () => {
  it("moves the word target with the slider on the blank path", async () => {
    const router = renderStructure();
    await screen.findByRole("heading", { level: 1 });

    const slider = screen.getByRole("slider", { name: de["setup.structure.preview.wordsLabel"] });
    expect(
      screen.getByText(t("setup.structure.preview.wordsDisplay", { count: 65000 })),
    ).toBeTruthy();

    fireEvent.change(slider, { target: { value: "90000" } });
    await waitFor(() => expect(address(router).words).toBe(90000));
    expect(
      screen.getByText(t("setup.structure.preview.wordsDisplay", { count: 90000 })),
    ).toBeTruthy();
  });

  it("shows the target read-only on the demo path — no slider", async () => {
    renderStructure("/setup/structure?demo=dead-signal");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByRole("slider")).toBeNull();
    expect(
      screen.getByText(t("setup.structure.preview.wordsDisplay", { count: 65000 })),
    ).toBeTruthy();
  });

  it("cycles the typology group with the arrow keys — the move selects", async () => {
    const router = renderStructure();
    await screen.findByRole("heading", { level: 1 });

    const first = typologyRadio("plotter");
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowDown" });
    await waitFor(() => expect(address(router).typology).toBe("pantser"));
    expect(typologyRadio("pantser").getAttribute("aria-checked")).toBe("true");
  });
});

/** A fresh render for the "form alone" leg of the validation test. */
function renderStructureAfterCleanup() {
  cleanup();
  renderStructure();
}
