// @vitest-environment jsdom
/**
 * The wizard's third step, driven through the real router over the real root
 * route (the StructureStep.test.tsx pattern): the answers ride search params,
 * so every assertion about state is an assertion about the address a refresh
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
import { t } from "@shell/lib/i18n";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

import { storePreSetupLocale } from "../preSetupLocale";
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

function renderAiRules(entry = "/setup/ai-rules") {
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
const continueButton = () => screen.getByRole("button", { name: de["setup.aiRules.continue"] });
const backButton = () => screen.getByRole("link", { name: de["setup.aiRules.back"] });
const roleRadio = (key: "archivar" | "lektor" | "coautor" | "sparring") =>
  screen.getByRole("radio", { name: de[`setup.aiRules.role.${key}.label`] });
const canonSlider = () => screen.getByRole("slider", { name: de["setup.aiRules.canon.label"] });
/** A native range speaks its stop through the value property, not an attribute. */
const canonValue = () => (canonSlider() as HTMLInputElement).value;

/** The address as the wizard's seam reads it. */
function address(router: ReturnType<typeof renderAiRules>): Record<string, unknown> {
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

describe("the AI-rules step — the draft's catalog", () => {
  it("renders the four roles with their meta lines and the tab title", async () => {
    renderAiRules();

    expect(
      await screen.findByRole("heading", { level: 1, name: de["setup.aiRules.heroTitle"] }),
    ).toBeTruthy();
    expect(document.title).toBe(`${de["setup.aiRules"]} — ${t("app.title")}`);

    // The four roles, by their drafted labels, in the draft's order.
    for (const key of ["archivar", "lektor", "coautor", "sparring"] as const) {
      expect(roleRadio(key)).toBeTruthy();
    }

    // The four meta lines the brief binds.
    expect(screen.getByText(de["setup.aiRules.role.archivar.meta"])).toBeTruthy();
    expect(screen.getByText(de["setup.aiRules.role.lektor.meta"])).toBeTruthy();
    expect(screen.getByText(de["setup.aiRules.role.coautor.meta"])).toBeTruthy();
    expect(screen.getByText(de["setup.aiRules.role.sparring.meta"])).toBeTruthy();

    // The recommendation badge sits on the lektor card, the draft's own.
    expect(screen.getByText(de["setup.aiRules.role.recommended"])).toBeTruthy();

    // The two section headings and the audit card's honest title.
    expect(screen.getByText(de["setup.aiRules.role.title"])).toBeTruthy();
    expect(screen.getByText(de["setup.aiRules.canon.title"])).toBeTruthy();
    expect(screen.getByText(de["setup.aiRules.audit.title"])).toBeTruthy();
  });

  it("speaks the du-tone in the rendered German intro", async () => {
    renderAiRules();
    const body = await screen.findByText(de["setup.aiRules.heroBody"]);
    expect(body.textContent).toContain("deine");
  });

  it("marks step three active and steps one and two done in the stepper", async () => {
    renderAiRules();
    await screen.findByRole("heading", { level: 1 });

    const stepper = screen.getByRole("navigation", { name: de["setup.wizard.progress"] });
    for (const key of ["setup.wizard.step1", "setup.wizard.step2", "setup.wizard.step3", "setup.wizard.step4"] as const) {
      expect(within(stepper).getByText(de[key])).toBeTruthy();
    }
    expect(
      within(stepper).getByText(de["setup.wizard.step3"]).closest("[aria-current]")?.getAttribute("aria-current"),
    ).toBe("step");
    // Steps one and two are done: they carry the check, not the active ring.
    expect(within(stepper).getByText(de["setup.wizard.step1"]).closest("[aria-current]")).toBeNull();
    expect(within(stepper).getByText(de["setup.wizard.step2"]).closest("[aria-current]")).toBeNull();
  });
});

describe("the AI-rules step — selection and the address", () => {
  it("keeps continue disabled until a role is chosen — the canon default stands", async () => {
    renderAiRules();
    await screen.findByRole("heading", { level: 1 });

    // The canon default (3) is materialized, so only the role gates the door.
    await waitFor(() => expect(canonValue()).toBe("3"));
    expect(continueButton().hasAttribute("disabled")).toBe(true);

    fireEvent.click(roleRadio("coautor"));
    await waitFor(() => expect(roleRadio("coautor").getAttribute("aria-checked")).toBe("true"));
    expect(continueButton().hasAttribute("disabled")).toBe(false);
  });

  it("persists the role and the canon into the address", async () => {
    const router = renderAiRules();
    await screen.findByRole("heading", { level: 1 });

    fireEvent.click(roleRadio("sparring"));
    fireEvent.change(canonSlider(), { target: { value: "5" } });
    await waitFor(() => expect(address(router).role).toBe("sparring"));
    expect(address(router).canon).toBe(5);
  });

  it("restores both answers from the address — the refresh shape", async () => {
    renderAiRules("/setup/ai-rules?role=coautor&canon=5");
    await screen.findByRole("heading", { level: 1 });

    expect(roleRadio("coautor").getAttribute("aria-checked")).toBe("true");
    expect(canonValue()).toBe("5");
    expect(screen.getByText(t("setup.aiRules.canon.badge", { n: 5 }))).toBeTruthy();
    expect(continueButton().hasAttribute("disabled")).toBe(false);
  });

  it("materializes the balanced default (3) into the address on a fresh visit", async () => {
    const router = renderAiRules();
    await screen.findByRole("heading", { level: 1 });

    await waitFor(() => expect(address(router).canon).toBe(3));
    expect(canonValue()).toBe("3");
    expect(screen.getByText(t("setup.aiRules.canon.badge", { n: 3 }))).toBeTruthy();
    // No role is preselected: the address is the only source of a selection.
    expect(address(router).role).toBeUndefined();
  });

  it("back to step two keeps the accumulated state", async () => {
    const router = renderAiRules("/setup/ai-rules?demo=dead-signal&typology=plotter&form=three-act");
    await screen.findByRole("heading", { level: 1 });

    fireEvent.click(roleRadio("lektor"));
    fireEvent.change(canonSlider(), { target: { value: "4" } });
    await waitFor(() => expect(continueButton().hasAttribute("disabled")).toBe(false));

    fireEvent.click(backButton());
    await waitFor(() => expect(router.state.location.pathname).toBe("/setup/structure"));
    expect(router.state.location.search).toMatchObject({
      demo: "dead-signal",
      typology: "plotter",
      form: "three-act",
      role: "lektor",
      canon: 4,
    });
  });

  it("forward to step four carries the state", async () => {
    const router = renderAiRules();
    await screen.findByRole("heading", { level: 1 });

    fireEvent.click(roleRadio("archivar"));
    await waitFor(() => expect(continueButton().hasAttribute("disabled")).toBe(false));

    fireEvent.click(continueButton());
    await waitFor(() => expect(router.state.location.pathname).toBe("/setup/provisioning"));
    expect(router.state.location.search).toMatchObject({ role: "archivar", canon: 3 });
  });
});

describe("the AI-rules step — the canon slider and the keyboard", () => {
  it("is a native five-stop range with the three drafted labels", async () => {
    renderAiRules();
    await screen.findByRole("heading", { level: 1 });

    const slider = canonSlider();
    expect(slider.getAttribute("type")).toBe("range");
    expect(slider.getAttribute("min")).toBe("1");
    expect(slider.getAttribute("max")).toBe("5");
    expect(slider.getAttribute("step")).toBe("1");

    // The three descriptive stops the draft labels.
    expect(screen.getByText(de["setup.aiRules.canon.tolerant"])).toBeTruthy();
    expect(screen.getByText(de["setup.aiRules.canon.balanced"])).toBeTruthy();
    expect(screen.getByText(de["setup.aiRules.canon.strict"])).toBeTruthy();
    expect(screen.getByText(de["setup.aiRules.canon.tolerantNote"])).toBeTruthy();
    expect(screen.getByText(de["setup.aiRules.canon.balancedNote"])).toBeTruthy();
    expect(screen.getByText(de["setup.aiRules.canon.strictNote"])).toBeTruthy();
  });

  it("steps with the arrow keys and jumps with Home/End — the move writes the address", async () => {
    const router = renderAiRules();
    await screen.findByRole("heading", { level: 1 });
    await waitFor(() => expect(address(router).canon).toBe(3));

    const slider = canonSlider();
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    await waitFor(() => expect(address(router).canon).toBe(4));
    fireEvent.keyDown(slider, { key: "ArrowLeft" });
    await waitFor(() => expect(address(router).canon).toBe(3));
    fireEvent.keyDown(slider, { key: "Home" });
    await waitFor(() => expect(address(router).canon).toBe(1));
    fireEvent.keyDown(slider, { key: "End" });
    await waitFor(() => expect(address(router).canon).toBe(5));
    // The ends clamp: a further step right stays at five.
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    await waitFor(() => expect(address(router).canon).toBe(5));
  });

  it("cycles the role group with the arrow keys — the move selects", async () => {
    const router = renderAiRules();
    await screen.findByRole("heading", { level: 1 });

    const first = roleRadio("archivar");
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowDown" });
    await waitFor(() => expect(address(router).role).toBe("lektor"));
    expect(roleRadio("lektor").getAttribute("aria-checked")).toBe("true");
  });
});

describe("the AI-rules step — the honest audit card", () => {
  it("carries the neutral audit wording and no invented metric or entity names", async () => {
    renderAiRules("/setup/ai-rules?demo=dead-signal");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.getByText(de["setup.aiRules.audit.body"])).toBeTruthy();
    // The draft's static „92% Bindungsgrad" is invented data: it stays out.
    expect(screen.queryByText(/Bindungsgrad/)).toBeNull();
    expect(screen.queryByText(/92/)).toBeNull();
    // No entity, station or character examples anywhere on the step.
    expect(screen.queryByText(/Entitäten/)).toBeNull();
    expect(screen.queryByText(/Knoten/)).toBeNull();
  });
});

describe("the AI-rules step's header", () => {
  it("keeps the draft's DE|EN|FR switcher working before setup", async () => {
    renderAiRules();
    await screen.findByRole("heading", { level: 1 });

    const group = screen.getByRole("radiogroup", { name: de["setup.welcome.language"] });
    const radios = within(group).getAllByRole("radio");
    expect(radios.map((radio) => radio.textContent)).toEqual(["DE", "EN", "FR"]);
    expect(radios[0].getAttribute("aria-checked")).toBe("true");

    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await screen.findByRole("heading", { level: 1, name: catalogs.en["setup.aiRules.heroTitle"] });
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } });
  });
});
