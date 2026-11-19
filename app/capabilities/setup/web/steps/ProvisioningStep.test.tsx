// @vitest-environment jsdom
/**
 * The wizard's fourth step — the one real POST — driven through the real
 * router over the real root route with the generated capability table (the
 * 409 routes home to writing's `/` shelf, so the real composition is mounted).
 * The answers ride search params, so the POST body is asserted against the
 * address a refresh would land on. Only the API client is mocked at its
 * module boundary; the mock keeps the backend's contract: 201 carries the
 * SetupResult facts, 409 means the instance is already complete (the shelf,
 * never a re-post), and the settings row exists once setup has run, so the
 * locale mirror's carry-over PATCH succeeds.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode } from "react";
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
import { capabilityRoutes } from "@shell/lib/generated/routes";
import { t } from "@shell/lib/i18n";
import { applyLocale, chosenLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

import { storePreSetupLocale } from "@shell/lib/preSetupLocale";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The backend's SetupResult for the dead-signal demo path — the facts the
 *  checklist must render exactly, no invented numbers. */
const RESULT = {
  novel_id: "11111111-1111-1111-1111-111111111111",
  novel_title: "Dead Signal",
  genre: "Science Fiction",
  target_words: 65_000,
  author_typology: "plotter",
  dramatic_form: "three-act",
  ai_role: "lektor",
  canon_strictness: 3,
  chapters: 7,
};

/** The novel row the novels endpoint answers after a 409 routes home — the
 *  shelf key the step invalidates; Task 6's shelf reads it. */
const NOVEL_ROW = {
  id: RESULT.novel_id,
  title: RESULT.novel_title,
  genre: RESULT.genre,
  chapter_count: RESULT.chapters,
  word_count: 0,
  author: null,
  blurb: null,
  language: "en",
  created_at: "2026-11-14T10:00:00Z",
  updated_at: "2026-11-14T10:00:00Z",
  last_exported_at: null,
};

/** The instance flips complete on a successful POST or a 409 — the status
 *  the `/` gate re-reads after the invalidation. */
let instanceComplete = false;

/** The settings row's locale, as the backend holds it: null until the seam's
 *  PATCH lands, the written choice from then on — so the refetch after the
 *  invalidation answers what the row truly holds, never a stale null. */
let rowLocale: string | null = null;

function scriptApi() {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: rowLocale, theme: null }, response: ok() };
    }
    if (path === "/api/setup/status") {
      return { data: { complete: instanceComplete }, response: ok() };
    }
    if (path === "/api/writing/novels") {
      return { data: [NOVEL_ROW], response: ok() };
    }
    throw new Error(`unexpected request: ${path}`);
  });
  api.POST.mockImplementation(async (path: string) => {
    if (path !== "/api/setup") throw new Error(`unexpected request: ${path}`);
    instanceComplete = true;
    return { data: RESULT, response: new Response(null, { status: 201 }) };
  });
  api.PATCH.mockImplementation(async (path: string, init?: { body?: { locale?: string } }) => {
    if (path !== "/api/settings") throw new Error(`unexpected request: ${path}`);
    // The row exists once setup has run: the seam's PATCH succeeds and the
    // choice becomes the row's own.
    rowLocale = init?.body?.locale ?? null;
    return { data: { locale: rowLocale, theme: null }, response: ok() };
  });
}

function renderProvisioning(entry: string, strict = false) {
  const router = createRouter({
    routeTree: rootRoute.addChildren([...capabilityRoutes]),
    history: createMemoryHistory({ initialEntries: [entry] }),
  });
  const tree = (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
  render(strict ? <StrictMode>{tree}</StrictMode> : tree);
  return router;
}

/** The step's controls, named by the German catalog the mirror adopts. */
const de = catalogs.de;
const workspaceButton = () => screen.getByRole("button", { name: de["setup.provisioning.cta.workspace"] });
const loreButton = () => screen.getByRole("button", { name: de["setup.provisioning.cta.lore"] });
const retryButton = () => screen.getByRole("button", { name: de["setup.provisioning.retry"] });
const backLink = () => screen.getByRole("link", { name: de["setup.provisioning.backToBasis"] });

/** A full blank-path address: raw title with padding, two genre pills, every
 *  setting away from its default so the POST body proves each field. */
const BLANK_ENTRY = `/setup/provisioning?title=${encodeURIComponent("  Der Klang des Eises  ")}&genres=${encodeURIComponent("Science Fiction & Speculative,Mystery & Noir")}&words=80000&typology=plantser&form=save-the-cat&role=coautor&canon=5`;
const DEMO_ENTRY = "/setup/provisioning?demo=dead-signal&title=ignored&typology=plotter&form=three-act&role=lektor&canon=3";

beforeEach(() => {
  instanceComplete = false;
  rowLocale = null;
  scriptApi();
  localStorage.clear();
  // The German visitor: the mirror is the pre-setup record; the seam must
  // carry it into the fresh row once the POST succeeds.
  storePreSetupLocale("de");
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  applyLocale(null);
  localStorage.clear();
});

describe("the provisioning step — the one POST", () => {
  it("posts the wizard's answers once on arrival — trimmed title, joined genre, every setting", async () => {
    renderProvisioning(BLANK_ENTRY);

    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(1));
    expect(api.POST).toHaveBeenCalledWith("/api/setup", {
      body: {
        novel_title: "Der Klang des Eises",
        demo: undefined,
        genre: "Science Fiction & Speculative, Mystery & Noir",
        target_words: 80000,
        author_typology: "plantser",
        dramatic_form: "save-the-cat",
        ai_role: "coautor",
        canon_strictness: 5,
      },
    });
    // The address keeps the raw title — the trim happens at the POST boundary.
    await screen.findByText(de["setup.provisioning.bound.item1"]);
  });

  it("posts exactly once under StrictMode's double effect", async () => {
    renderProvisioning(DEMO_ENTRY, true);

    await screen.findByText(de["setup.provisioning.bound.item1"]);
    expect(api.POST).toHaveBeenCalledTimes(1);
  });

  it("the demo path posts the archive's slug and title — no genre beside it", async () => {
    renderProvisioning(DEMO_ENTRY);

    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(1));
    expect(api.POST).toHaveBeenCalledWith("/api/setup", {
      body: {
        novel_title: "Dead Signal",
        demo: "dead-signal",
        genre: undefined,
        target_words: 65000,
        author_typology: "plotter",
        dramatic_form: "three-act",
        ai_role: "lektor",
        canon_strictness: 3,
      },
    });
  });

  it("an empty deep link falls back to the basis without posting", async () => {
    const router = renderProvisioning("/setup/provisioning");

    await screen.findByRole("heading", { level: 1, name: de["setup.basis.heroTitle"] });
    expect(router.state.location.pathname).toBe("/setup/basis");
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("409 routes to the shelf and never re-posts", async () => {
    api.POST.mockImplementation(async () => {
      instanceComplete = true;
      return {
        error: { detail: "setup already complete" },
        response: new Response(null, { status: 409 }),
      };
    });
    const router = renderProvisioning(DEMO_ENTRY);

    // The gate re-reads the invalidated status and answers with the shelf —
    // writing's `/` surface after the W3 handover, never a re-post. The
    // catalog read rides waitFor so it re-evaluates once the mirror adoption
    // has settled the language (the step flips it mid-flow).
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 1, name: t("writing.shelf.title") })).toBeTruthy(),
    );
    expect(router.state.location.pathname).toBe("/");
    expect(api.POST).toHaveBeenCalledTimes(1);
    const statusAsks = api.GET.mock.calls.filter(([path]) => path === "/api/setup/status");
    expect(statusAsks.length).toBeGreaterThanOrEqual(2);
  });
});

describe("the provisioning step — the checklist renders the response's facts", () => {
  it("renders exactly the SetupResult facts — chapters, form label, role label, typography", async () => {
    renderProvisioning(DEMO_ENTRY);

    expect(await screen.findByText(de["setup.provisioning.bound.item1"])).toBeTruthy();
    expect(screen.getByText(de["setup.provisioning.bound.item2"])).toBeTruthy();
    expect(screen.getByText(de["setup.provisioning.bound.item3"])).toBeTruthy();
    expect(screen.getByText(de["setup.provisioning.bound.item4"])).toBeTruthy();

    // Item 1: the effective genre and the localized form label.
    expect(
      screen.getByText(`${RESULT.genre} • ${de["setup.structure.form.threeAct.label"]}`),
    ).toBeTruthy();
    // Item 2: the response's chapter count, nothing invented.
    expect(screen.getByText(t("setup.provisioning.bound.item2Status", { count: 7 }))).toBeTruthy();
    // Item 3: the role label, localized from the response's id.
    expect(screen.getByText(de["setup.aiRules.role.lektor.label"])).toBeTruthy();
    // Item 4: the drafted typography constants — the prose surface's own.
    expect(screen.getByText(de["setup.provisioning.bound.typography"])).toBeTruthy();
    // The completion face: the bar is full only once the POST has landed.
    expect(screen.getByText(de["setup.provisioning.bound.complete"])).toBeTruthy();
    expect(screen.getByText(de["setup.provisioning.bound.ready"])).toBeTruthy();
  });

  it("the blank path's zero chapters and absent answers render honestly", async () => {
    api.POST.mockImplementation(async () => {
      instanceComplete = true;
      return {
        data: {
          ...RESULT,
          novel_title: "Der Klang des Eises",
          genre: null,
          dramatic_form: null,
          ai_role: null,
          chapters: 0,
        },
        response: new Response(null, { status: 201 }),
      };
    });
    renderProvisioning(`/setup/provisioning?title=${encodeURIComponent("Der Klang des Eises")}`);

    // Await the bound face by its catalog literal first: the step suspends
    // on the status ask, so the mirror's adoption (and with it the catalog
    // language `t` formats in) lands with the first paint, not before it.
    expect(await screen.findByText(de["setup.provisioning.bound.item1"])).toBeTruthy();
    expect(screen.getByText(t("setup.provisioning.bound.item2Status", { count: 0 }))).toBeTruthy();
    // No genre, no form, no role: the two meta slots answer with a dash,
    // never with an invented label.
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("marks step four active and steps one to three done in the stepper", async () => {
    renderProvisioning(DEMO_ENTRY);
    await screen.findByText(de["setup.provisioning.bound.item1"]);

    const stepper = screen.getByRole("navigation", { name: de["setup.wizard.progress"] });
    expect(
      within(stepper).getByText(de["setup.wizard.step4"]).closest("[aria-current]")?.getAttribute("aria-current"),
    ).toBe("step");
    for (const key of ["setup.wizard.step1", "setup.wizard.step2", "setup.wizard.step3"] as const) {
      const done = within(stepper).getByText(de[key]);
      expect(done.closest("[aria-current]")).toBeNull();
      expect(done.closest("a")).not.toBeNull();
    }
  });

  it("names the tab and speaks the du-tone", async () => {
    renderProvisioning(DEMO_ENTRY);
    await screen.findByText(de["setup.provisioning.bound.item1"]);

    expect(document.title).toBe(`${de["setup.provisioning"]} — ${t("app.title")}`);
    expect(screen.getByText(de["setup.provisioning.heroBody"]).textContent).toContain("deine");
  });
});

describe("the provisioning step — the loading state (states-reference panel 3)", () => {
  it("shows the binding checklist while the POST is in flight — no percentage, CTAs disabled", async () => {
    let resolvePost!: (value: { data: typeof RESULT; response: Response }) => void;
    api.POST.mockImplementationOnce(
      () =>
        new Promise<{ data: typeof RESULT; response: Response }>((resolve) => {
          resolvePost = resolve;
        }),
    );
    renderProvisioning(DEMO_ENTRY);

    // The active item spins with the drafted status; items four and five wait.
    expect(await screen.findByText(de["setup.provisioning.loading.item3Status"])).toBeTruthy();
    expect(screen.getByText(de["setup.provisioning.loading.item1"])).toBeTruthy();
    expect(screen.getByText(de["setup.provisioning.loading.item2"])).toBeTruthy();
    expect(screen.getByText(de["setup.provisioning.loading.item4"])).toBeTruthy();
    expect(screen.getByText(de["setup.provisioning.loading.item5"])).toBeTruthy();
    expect(screen.getAllByText(de["setup.provisioning.loading.pending"])).toHaveLength(2);
    // The chapter count pre-response comes from the demo manifest only.
    expect(screen.getByText(t("setup.basis.demoChapters", { count: 7 }))).toBeTruthy();
    // Honest progress: no percentage anywhere while the work is outstanding.
    expect(screen.queryByText(/%/)).toBeNull();
    expect(screen.getByText(de["setup.provisioning.loading.sync"])).toBeTruthy();
    // Both CTAs stay disabled during the binding.
    expect(workspaceButton().hasAttribute("disabled")).toBe(true);
    expect(loreButton().hasAttribute("disabled")).toBe(true);

    resolvePost({ data: RESULT, response: new Response(null, { status: 201 }) });
    expect(await screen.findByText(de["setup.provisioning.bound.item1"])).toBeTruthy();
  });

  it("the blank path's pre-response chapter slot stays neutral", async () => {
    let resolvePost!: (value: { data: typeof RESULT; response: Response }) => void;
    api.POST.mockImplementationOnce(
      () =>
        new Promise<{ data: typeof RESULT; response: Response }>((resolve) => {
          resolvePost = resolve;
        }),
    );
    renderProvisioning(`/setup/provisioning?title=${encodeURIComponent("Der Klang des Eises")}`);

    expect(await screen.findByText(de["setup.provisioning.loading.item3Status"])).toBeTruthy();
    // No manifest, no count: the slot answers with a dash, not a guess.
    expect(screen.getByText("—")).toBeTruthy();

    resolvePost({ data: RESULT, response: new Response(null, { status: 201 }) });
    await screen.findByText(de["setup.provisioning.bound.item1"]);
  });
});

describe("the provisioning step — the header locks while the book binds", () => {
  it("in flight: the stepper offers no links, the done steps are disabled, the switcher stays live", async () => {
    let resolvePost!: (value: { data: typeof RESULT; response: Response }) => void;
    api.POST.mockImplementationOnce(
      () =>
        new Promise<{ data: typeof RESULT; response: Response }>((resolve) => {
          resolvePost = resolve;
        }),
    );
    renderProvisioning(DEMO_ENTRY);

    expect(await screen.findByText(de["setup.provisioning.loading.item3Status"])).toBeTruthy();
    const stepper = screen.getByRole("navigation", { name: de["setup.wizard.progress"] });
    // The POST commits the answers: walking back to edit them must wait.
    // The done steps keep their check and label but stop being links.
    expect(within(stepper).queryAllByRole("link")).toHaveLength(0);
    for (const key of ["setup.wizard.step1", "setup.wizard.step2", "setup.wizard.step3"] as const) {
      const done = within(stepper).getByText(de[key]);
      expect(done.closest("[aria-disabled]")?.getAttribute("aria-disabled")).toBe("true");
    }
    // The lock is the stepper's alone: the switcher stays as it is.
    expect(screen.getByRole("radiogroup", { name: de["shell.language"] })).toBeTruthy();

    // Once the POST lands, the done steps link again.
    resolvePost({ data: RESULT, response: new Response(null, { status: 201 }) });
    await screen.findByText(de["setup.provisioning.bound.item1"]);
    const unlocked = screen.getByRole("navigation", { name: de["setup.wizard.progress"] });
    expect(within(unlocked).getAllByRole("link")).toHaveLength(3);
  });

  it("a refused binding unlocks the stepper again — the way back stays real", async () => {
    api.POST.mockImplementationOnce(async () => {
      throw new Error("offline");
    });
    renderProvisioning(DEMO_ENTRY);

    await screen.findByRole("alert");
    const stepper = screen.getByRole("navigation", { name: de["setup.wizard.progress"] });
    expect(within(stepper).getAllByRole("link")).toHaveLength(3);
  });
});

describe("the provisioning step — the failure card (states-reference panel 4)", () => {
  it("names the failure honestly and retry re-posts", async () => {
    api.POST.mockImplementationOnce(async () => {
      throw new Error("offline");
    });
    renderProvisioning(`/setup/provisioning?title=${encodeURIComponent("Der Klang des Eises")}&role=lektor`);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(de["setup.provisioning.failedTitle"]);
    expect(alert.textContent).toContain(de["setup.provisioning.failedBody"]);
    expect(alert.textContent).toContain(de["setup.provisioning.cause.network"]);
    // Nothing is marked complete: the POST is atomic, no stopped checklist
    // with false check marks.
    expect(screen.queryByText(de["setup.provisioning.bound.item1"])).toBeNull();

    fireEvent.click(retryButton());
    expect(await screen.findByText(de["setup.provisioning.bound.item1"])).toBeTruthy();
    expect(api.POST).toHaveBeenCalledTimes(2);
  });

  it("an HTTP refusal names its status as the cause", async () => {
    api.POST.mockImplementationOnce(async () => ({
      data: undefined,
      response: new Response(null, { status: 503 }),
    }));
    renderProvisioning(DEMO_ENTRY);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("503");
    expect(alert.textContent).toContain(de["setup.provisioning.failedTitle"]);
  });

  it("back to step one keeps the accumulated state", async () => {
    api.POST.mockImplementationOnce(async () => {
      throw new Error("offline");
    });
    const router = renderProvisioning(DEMO_ENTRY);

    await screen.findByRole("alert");
    fireEvent.click(backLink());
    await waitFor(() => expect(router.state.location.pathname).toBe("/setup/basis"));
    expect(router.state.location.search).toMatchObject({
      demo: "dead-signal",
      typology: "plotter",
      form: "three-act",
      role: "lektor",
      canon: 3,
    });
  });
});

describe("the provisioning step — the locale seam and the bound actions", () => {
  it("carries the mirror into the fresh row after the POST, then clears it", async () => {
    storePreSetupLocale("fr");
    renderProvisioning(DEMO_ENTRY);

    // The mirror is adopted before paint: the checklist speaks French.
    const fr = catalogs.fr;
    expect(await screen.findByText(fr["setup.provisioning.bound.item1"])).toBeTruthy();
    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "fr" } }),
    );
    // The seam runs after the POST, never before it.
    expect(api.POST.mock.invocationCallOrder[0]).toBeLessThan(api.PATCH.mock.invocationCallOrder[0]);
    await waitFor(() => expect(localStorage.getItem("narrare.locale.preSetup")).toBeNull());
    // The row now holds the choice: the settings refetch adopts it, so the
    // checklist still speaks French — no flash back to the browser's language.
    await waitFor(() => expect(chosenLocale()).toBe("fr"));
    expect(screen.getByText(fr["setup.provisioning.bound.item1"])).toBeTruthy();
  });

  it("a refused carry-over keeps the mirror — no locale flash", async () => {
    storePreSetupLocale("fr");
    api.PATCH.mockImplementation(async () => ({
      error: { detail: "refused" },
      response: new Response(null, { status: 500 }),
    }));
    renderProvisioning(DEMO_ENTRY);

    const fr = catalogs.fr;
    expect(await screen.findByText(fr["setup.provisioning.bound.item1"])).toBeTruthy();
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(localStorage.getItem("narrare.locale.preSetup")).toBe("fr");
  });

  it("the bound actions: workspace and lore honestly disabled, the way home real", async () => {
    renderProvisioning(DEMO_ENTRY);
    await screen.findByText(de["setup.provisioning.bound.item1"]);

    expect(workspaceButton().hasAttribute("disabled")).toBe(true);
    expect(loreButton().hasAttribute("disabled")).toBe(true);
    expect(screen.getAllByText(de["setup.welcome.comingSoon"]).length).toBeGreaterThanOrEqual(1);
    const home = screen.getByRole("link", { name: de["setup.provisioning.cta.back"] });
    expect(home.getAttribute("href")).toBe("/");
  });
});
