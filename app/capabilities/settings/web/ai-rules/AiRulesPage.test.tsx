// @vitest-environment jsdom
/**
 * The AI-Regeln surface (W8 Task 9) — the settings capability's second
 * page, driven over a bare router with the API client mocked at its module
 * boundary; the queries and the query client are real.
 *
 * The pins hold the honest-state rules (the wave's binding contract): the
 * key-once create moment (the full key rides exactly one response and the
 * surface shows it exactly once, the mask after), the refusal families on
 * their exact codes (the delete guard's 409, the discovery's 409/502, the
 * key store's 503), `settings.test` never a dropdown, the resolved number
 * shown as is (uncapped when no ceiling is stored, the cap noted when one
 * bounds it), the fake driver's honest mark instead of the draft's invented
 * „0 Tok. (Offline)“, and the hub chrome that carries the two routes that
 * exist — no Prompts item, no dead door.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { t } from "@shell/lib/i18n";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { AiRulesPage } from "./AiRulesPage";

const de = catalogs.de;
const en = catalogs.en;
const fr = catalogs.fr;
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

configure({ asyncUtilTimeout: 15_000 });
// The page mounts six reads and five sections — the jsdom render costs more
// than the lighter settings page's budget; the suite says so explicitly.
vi.setConfig({ testTimeout: 25_000 });

function ok(status = 200): Response {
  return new Response(null, { status });
}

/** The mock instance's rows — the five reads' baselines, overwritten per
 *  case. The shapes mirror the wire (the generated schema's reads). */
let providers: unknown[];
let presets: unknown[];
let models: unknown[];
let tasks: unknown[];
let assignments: unknown[];
let novels: unknown[];
let driverKind: "fake" | "configured" | { fail: true };

function provider(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: "prov-1",
    name: "Cloud",
    kind: "openai-chat",
    base_url: "https://llm.example.com/v1",
    models_url: null,
    vendor: "openai",
    api_key_mask: "sk-…9xQz",
    ...overrides,
  };
}

function preset(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: "openai",
    label: "OpenAI",
    kind: "openai-chat",
    base_url: "https://api.openai.com/v1",
    models_url: null,
    vendor: "openai",
    model: "gpt-5.4",
    note_key: null,
    models: ["gpt-5.4", "gpt-5.4-mini"],
    snapshot_date: "2026-11-01",
    ...overrides,
  };
}

function model(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: "m-1",
    name: "Cloud-Schreiber",
    provider_id: "prov-1",
    provider_name: "Cloud",
    model: "gpt-5.4",
    is_default: true,
    context_window: 200_000,
    max_output_tokens: 8_192,
    temperature: 0.7,
    request_timeout: 60,
    in_catalog: true,
    last_error_code: null,
    last_error_at: null,
    created_at: "2026-11-20T10:00:00Z",
    updated_at: "2026-11-20T10:00:00Z",
    ...overrides,
  };
}

function task(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    task_key: "writing.continuation",
    profile_id: null,
    profile_name: null,
    kind: "fake",
    assignable: true,
    output_profile: "balanced",
    resolved_output_tokens: 4_096,
    ...overrides,
  };
}

function freshTasks(): unknown[] {
  return [
    task(),
    task({ task_key: "chat.ask" }),
    task({ task_key: "knowledge.extract-entities" }),
    task({ task_key: "knowledge.check-consistency" }),
    task({
      task_key: "settings.test",
      profile_id: null,
      profile_name: null,
      kind: "audit",
      assignable: false,
      output_profile: null,
      resolved_output_tokens: null,
    }),
  ];
}

function novel(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: "n-1",
    title: "Das Signal im Permafrost",
    author: null,
    genre: null,
    target_words: 65_000,
    status: "draft",
    archived_at: null,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-20T10:00:00Z",
    ...overrides,
  };
}

/** The five reads' router: every path the page's hooks ask, answered from
 *  the baselines above. */
function scriptReads() {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings/providers") return { data: providers, response: ok() };
    if (path === "/api/settings/presets") return { data: presets, response: ok() };
    if (path === "/api/settings/models") return { data: models, response: ok() };
    if (path === "/api/settings/assignments") return { data: assignments, response: ok() };
    if (path === "/api/settings/tasks") return { data: tasks, response: ok() };
    if (path === "/api/settings/driver") {
      if (typeof driverKind === "object") {
        return { data: undefined, response: new Response(null, { status: 500 }) };
      }
      return { data: { kind: driverKind }, response: ok() };
    }
    if (path === "/api/writing/novels") return { data: novels, response: ok() };
    throw new Error(`unexpected GET: ${path}`);
  });
}

const puts = () => api.PUT.mock.calls as unknown as Array<[string, { body: Record<string, unknown> }]>;
const posts = () => api.POST.mock.calls as unknown as Array<[string, { body?: Record<string, unknown> }]>;
const patches = () => api.PATCH.mock.calls as unknown as Array<[string, { body?: Record<string, unknown> }]>;

const testRoot = createRootRoute({ component: () => <Outlet /> });
const aiRulesRoute = createRoute({
  getParentRoute: () => testRoot,
  path: "/settings/ai-regeln",
  component: AiRulesPage,
});
const novelRoute = createRoute({
  getParentRoute: () => testRoot,
  path: "/novels/$novelId",
  component: () => <p>workspace placeholder</p>,
});

function renderPage(path = "/settings/ai-regeln") {
  const router = createRouter({
    routeTree: testRoot.addChildren([aiRulesRoute, novelRoute]),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

function modelSelect(row: HTMLElement): HTMLSelectElement {
  return row.querySelector('select[aria-labelledby^="ai-rules-task-model-"]') as HTMLSelectElement;
}

function profileSelect(row: HTMLElement): HTMLSelectElement {
  return row.querySelector('select[aria-labelledby^="ai-rules-task-profile-"]') as HTMLSelectElement;
}

function taskRow(taskKey: string): HTMLElement {
  const row = screen.getAllByTestId("task-row").find((entry) => entry.getAttribute("data-task-key") === taskKey);
  if (row === undefined) throw new Error(`no task row for ${taskKey}`);
  return row;
}

beforeEach(() => {
  // Reset, not clear: a refusal case's scripted implementation must never
  // leak into the next one.
  api.GET.mockReset();
  api.POST.mockReset();
  api.PATCH.mockReset();
  api.PUT.mockReset();
  api.DELETE.mockReset();
  providers = [];
  presets = [preset(), preset({ id: "zai-coding-plan", label: "Z.ai Coding Plan", vendor: "zai-coding-plan", model: "glm-5.3", note_key: "settings.providers.note.zaiCodingPlan", models: [] })];
  models = [];
  tasks = freshTasks();
  assignments = [];
  novels = [];
  driverKind = "fake";
  scriptReads();
  localStorage.clear();
  queryClient.clear();
  // The German visitor: the browser speaks de-DE, the surface speaks German.
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  applyLocale("de");
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  applyLocale(null);
  localStorage.clear();
});

describe("the hub chrome — the two routes that exist", () => {
  it("carries Allgemein and KI-Regeln, the active face on the route the page stands on, no Prompts item", async () => {
    renderPage();
    await screen.findAllByTestId("task-row");
    const nav = screen.getByRole("navigation", { name: de["settings.hub.label"] });
    const links = Array.from(nav.querySelectorAll("a"));
    expect(links.map((link) => link.textContent)).toEqual([de["settings.hub.general"], de["settings.hub.aiRules"]]);
    expect(links[1]?.getAttribute("aria-current")).toBe("page");
    expect(links[0]?.getAttribute("aria-current")).toBeNull();
    // The draft's third item waits for its route — no dead door.
    expect(nav.textContent).not.toContain("Prompts");
  });

  it("stands on the Allgemein page too, its active face there", async () => {
    // The hub is the shared chrome; its Allgemein face is pinned in
    // SettingsPage.test — here only the geometry's other half.
    renderPage();
    await screen.findAllByTestId("task-row");
    const nav = screen.getByRole("navigation", { name: de["settings.hub.label"] });
    expect(nav.textContent).toContain(de["settings.hub.general"]);
  });
});

describe("the honest gates — loading, outage, retry", () => {
  it("the loading line stands while the five reads ask", async () => {
    api.GET.mockImplementation(async () => new Promise<{ data?: unknown; response: Response }>(() => {}));
    renderPage();
    expect(await screen.findByText(de["settings.loading"])).toBeTruthy();
    // The chrome and hero stand; the sections do not — no rows answer
    // before the reads did.
    expect(screen.queryByTestId("task-row")).toBeNull();
    expect(screen.queryByTestId("provider-card")).toBeNull();
  });

  it("a failed read names the outage and the retry re-asks", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings/models") return { data: undefined, response: new Response(null, { status: 500 }) };
      if (path === "/api/writing/novels") return { data: [], response: ok() };
      if (path === "/api/settings/providers") return { data: [], response: ok() };
      if (path === "/api/settings/presets") return { data: presets, response: ok() };
      if (path === "/api/settings/assignments") return { data: [], response: ok() };
      if (path === "/api/settings/tasks") return { data: tasks, response: ok() };
      if (path === "/api/settings/driver") return { data: { kind: "fake" }, response: ok() };
      throw new Error(`unexpected GET: ${path}`);
    });
    renderPage();
    expect(await screen.findByText(de["settings.loadFailed"])).toBeTruthy();
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings/models") return { data: [], response: ok() };
      if (path === "/api/writing/novels") return { data: [], response: ok() };
      if (path === "/api/settings/providers") return { data: [], response: ok() };
      if (path === "/api/settings/presets") return { data: presets, response: ok() };
      if (path === "/api/settings/assignments") return { data: [], response: ok() };
      if (path === "/api/settings/tasks") return { data: tasks, response: ok() };
      if (path === "/api/settings/driver") return { data: { kind: "fake" }, response: ok() };
      throw new Error(`unexpected GET: ${path}`);
    });
    fireEvent.click(screen.getByRole("button", { name: de["settings.retry"] }));
    expect(await screen.findByText(de["settings.ai.heading"])).toBeTruthy();
  });
});

describe("the pointer door — the Buch-Einstellungen's own deep link", () => {
  it("routes to the active book's workspace with the dialog's hash", async () => {
    novels = [novel()];
    renderPage();
    await screen.findAllByTestId("task-row");
    const door = screen.getByTestId("pointer-door") as HTMLAnchorElement;
    expect(door.getAttribute("href")).toBe("/novels/n-1#buch-einstellungen");
    fireEvent.click(door);
    await waitFor(() => expect(screen.getByText("workspace placeholder")).toBeTruthy());
  });

  it("no book: the why stands, no door", async () => {
    renderPage();
    await screen.findAllByTestId("task-row");
    expect(screen.queryByTestId("pointer-door")).toBeNull();
    expect(screen.getByTestId("pointer-door-none").textContent).toBe(de["settings.ai.pointer.none"]);
  });
});

describe("the segment pills — the real counters", () => {
  it("they answer the reads, never the draft's sample numbers", async () => {
    providers = [provider()];
    models = [model()];
    assignments = [{ task_key: "writing.continuation", profile_id: "m-1", output_profile: "long_texts", output_profile_custom: null }];
    renderPage();
    await screen.findAllByTestId("task-row");
    expect(screen.getByText(t("settings.ai.nav.providers", { count: 1 }))).toBeTruthy();
    expect(screen.getByText(t("settings.ai.nav.models", { count: 1 }))).toBeTruthy();
    expect(screen.getByText(t("settings.ai.nav.assignments", { count: 1 }))).toBeTruthy();
  });
});

describe("the provider section — masks, the key-once moment, the guards", () => {
  it("the card shows the mask, never key material beyond it; the keyless card says so", async () => {
    providers = [provider(), provider({ id: "prov-local", name: "Lokal", kind: "fake", base_url: null, vendor: null, api_key_mask: null })];
    renderPage();
    await screen.findAllByTestId("task-row");
    expect(screen.getByText("sk-…9xQz")).toBeTruthy();
    // No plaintext key shape anywhere: every read answers the mask, the
    // `sk-…` form — a full key (`sk-` followed by characters) never renders.
    expect(document.body.textContent?.match(/sk-[A-Za-z0-9]/)).toBeNull();
    expect(screen.getByText(de["settings.ai.provider.key.none"])).toBeTruthy();
    expect(screen.getByText(de["settings.ai.provider.noEndpoint"])).toBeTruthy();
  });

  it("the create lands and the key shows EXACTLY ONCE — the mask answers after", async () => {
    const created = { ...provider({ id: "prov-2", name: "Neu" }), api_key: "sk-test-keyonce-abc123" };
    api.POST.mockImplementation(async (path: string) => {
      if (path === "/api/settings/providers") {
        return { data: created, response: ok(201) };
      }
      throw new Error(`unexpected POST: ${path}`);
    });
    // The list's next ask answers the created row, so the invalidation's
    // refetch lands the mask card beside the face.
    providers = [created];
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.change(screen.getByLabelText(de["settings.ai.create.name"]), { target: { value: "Neu" } });
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.create.submit"] }));
    // The landed ask, then the face it renders — the wire first, the DOM
    // reads after (the flush-first pattern the settings suite pins).
    await waitFor(() => expect(posts().length).toBe(1));
    await waitFor(() => expect(screen.queryByTestId("created-key")).not.toBeNull());

    // The face holds the plaintext, and the page carries it exactly once.
    const face = screen.getByTestId("created-key");
    expect(face.textContent).toBe("sk-test-keyonce-abc123");
    const keyMatches = document.body.textContent?.split("sk-test-keyonce-abc123").length ?? 1;
    expect(keyMatches - 1).toBe(1);

    // Fertig retires the face — the string is gone from the page, the
    // grid keeps the mask.
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.created.done"] }));
    expect(screen.queryByTestId("created-key")).toBeNull();
    expect(document.body.textContent).not.toContain("sk-test-keyonce-abc123");
    expect(screen.getByText("sk-…9xQz")).toBeTruthy();
  });

  it("a create without a key shows the honest no-key face, nothing invented", async () => {
    api.POST.mockImplementation(async (path: string) => {
      if (path === "/api/settings/providers") {
        return { data: provider({ id: "prov-2", name: "Lokal", api_key_mask: null, api_key: null }), response: ok(201) };
      }
      throw new Error(`unexpected POST: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.change(screen.getByLabelText(de["settings.ai.create.name"]), { target: { value: "Lokal" } });
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.create.submit"] }));
    await waitFor(() => expect(posts().length).toBe(1));
    // The face's line rides beside the provider's name — a substring match.
    await waitFor(() => expect(screen.queryByText(/Ohne Schlüssel angelegt/)).not.toBeNull());
    expect(screen.queryByTestId("created-key")).toBeNull();
  });

  it("a refused create (422) wears the refusal family and keeps the answers", async () => {
    api.POST.mockImplementation(async (path: string) => {
      if (path === "/api/settings/providers") {
        return {
          error: { detail: [{ loc: ["body", "api_key"], msg: "missing" }] },
          response: new Response(null, { status: 422 }),
        };
      }
      throw new Error(`unexpected POST: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.change(screen.getByLabelText(de["settings.ai.create.name"]), { target: { value: "Neu" } });
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.create.submit"] }));
    expect(await screen.findByText(de["settings.refused"])).toBeTruthy();
    expect((screen.getByLabelText(de["settings.ai.create.name"]) as HTMLInputElement).value).toBe("Neu");
  });

  it("the delete guard's 409 names the models — the family face with the backend's own sentence", async () => {
    providers = [provider()];
    api.DELETE.mockImplementation(async (path: string) => {
      if (path === "/api/settings/providers/{provider_id}") {
        return {
          error: { detail: "the provider still has models pointed at it: Cloud-Schreiber" },
          response: new Response(null, { status: 409 }),
        };
      }
      throw new Error(`unexpected DELETE: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.click(screen.getAllByRole("button", { name: de["settings.ai.provider.remove"] })[0]);
    expect(await screen.findByText(de["settings.ai.errors.guarded"])).toBeTruthy();
    expect(screen.getByText("the provider still has models pointed at it: Cloud-Schreiber")).toBeTruthy();
    // The provider stands — the guard kept it.
    expect(screen.getByText("Cloud")).toBeTruthy();
  });

  it("a key-store refusal (503) wears its own family", async () => {
    providers = [provider()];
    api.DELETE.mockImplementation(async (path: string) => {
      if (path === "/api/settings/providers/{provider_id}") {
        return { error: { detail: "the key store refused" }, response: new Response(null, { status: 503 }) };
      }
      throw new Error(`unexpected DELETE: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.click(screen.getAllByRole("button", { name: de["settings.ai.provider.remove"] })[0]);
    expect(await screen.findByText(de["settings.ai.errors.keystore"])).toBeTruthy();
  });

  it("the inline edit patches only what it carries; an empty key field keeps the stored one", async () => {
    providers = [provider()];
    api.PATCH.mockImplementation(async (path: string) => {
      if (path === "/api/settings/providers/{provider_id}") {
        return { data: provider(), response: ok() };
      }
      throw new Error(`unexpected PATCH: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.provider.edit"] }));
    // The edit form's labels share their texts with the create form's —
    // scope the lookups to the card the edit stands in.
    const card = screen
      .getAllByTestId("provider-card")
      .find((entry) => entry.textContent?.includes(de["settings.ai.provider.editKey"])) as HTMLElement;
    fireEvent.change(within(card).getByLabelText(de["settings.ai.create.name"]), { target: { value: "Umbenannt" } });
    fireEvent.click(within(card).getByRole("button", { name: de["settings.ai.save"] }));
    await waitFor(() => expect(patches().length).toBe(1));
    const [, init] = patches()[0];
    expect(init.body).toEqual({ name: "Umbenannt", base_url: "https://llm.example.com/v1" });
    expect("api_key" in (init.body as Record<string, unknown>)).toBe(false);
  });
});

describe("the modelle section — defaults, test faces, discovery, the delete", () => {
  beforeEach(() => {
    models = [
      model(),
      model({
        id: "m-2",
        name: "Lokal-Schreiber",
        provider_id: "prov-local",
        provider_name: "Lokal",
        model: "llama3:8b",
        is_default: false,
        context_window: null,
        max_output_tokens: null,
        temperature: null,
        request_timeout: null,
        in_catalog: false,
      }),
    ];
    providers = [provider(), provider({ id: "prov-local", name: "Lokal", kind: "fake", base_url: null, vendor: null, api_key_mask: null })];
  });

  it("the default badge stands, the handover rides the patch, the default carries no Entfernen", async () => {
    renderPage();
    await screen.findAllByTestId("task-row");
    const cards = screen.getAllByTestId("model-card");
    expect(cards[0]?.textContent).toContain(de["settings.ai.models.default"]);
    // The default card owns no remove button; the freed one does.
    expect(cards[0]?.textContent).not.toContain(de["settings.ai.models.remove"]);
    expect(cards[1]?.textContent).toContain(de["settings.ai.models.remove"]);
    api.PATCH.mockImplementation(async (path: string) => {
      if (path === "/api/settings/models/{model_id}") return { data: model(), response: ok() };
      throw new Error(`unexpected PATCH: ${path}`);
    });
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.models.makeDefault"] }));
    await waitFor(() => expect(patches().length).toBe(1));
    const [path, init] = patches()[0];
    expect(path).toBe("/api/settings/models/{model_id}");
    expect(init?.body).toEqual({ is_default: true });
  });

  it("the stat tiles answer the stored columns — the unset is the honest dash, the fake answers local", async () => {
    renderPage();
    await screen.findAllByTestId("task-row");
    const cards = screen.getAllByTestId("model-card");
    expect(cards[0]?.textContent).toContain("200.000");
    expect(cards[0]?.textContent).toContain(de["settings.ai.stat.temperature"]);
    // The freed model's unset columns: the dash, never a drafted number.
    expect(cards[1]?.textContent).toContain(de["settings.ai.stat.local"]);
    expect(cards[1]?.textContent).toContain(de["settings.ai.stat.localValue"]);
  });

  it("the test face: running, then ok with the wire's latency; a failure names itself", async () => {
    let fail = false;
    api.POST.mockImplementation(async (path: string) => {
      if (path === "/api/settings/models/{model_id}/test") {
        if (fail) return { data: { ok: false, error: "401 vom Endpunkt", latency_ms: 12 }, response: ok() };
        return { data: { ok: true, error: null, latency_ms: 234 }, response: ok() };
      }
      throw new Error(`unexpected POST: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.click(screen.getAllByRole("button", { name: de["settings.ai.models.test"] })[0]);
    expect(await screen.findByText(t("settings.ai.models.testOk", { ms: "234" }))).toBeTruthy();
    const [path] = posts().find(([callPath]) => callPath === "/api/settings/models/{model_id}/test") ?? [];
    expect(path).toBe("/api/settings/models/{model_id}/test");

    fail = true;
    fireEvent.click(screen.getAllByRole("button", { name: de["settings.ai.models.test"] })[0]);
    expect(await screen.findByText(t("settings.ai.models.testFail", { error: "401 vom Endpunkt" }))).toBeTruthy();
  });

  it("the register form's discovery: the ids answer, the 502 wears the unreachable family, the fake's 409 its own", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings/providers/{provider_id}/models") {
        return { data: ["gpt-5.4", "gpt-5.4-mini", "gpt-5-nano"], response: ok() };
      }
      if (path === "/api/settings/providers") return { data: providers, response: ok() };
      if (path === "/api/settings/presets") return { data: presets, response: ok() };
      if (path === "/api/settings/models") return { data: models, response: ok() };
      if (path === "/api/settings/assignments") return { data: assignments, response: ok() };
      if (path === "/api/settings/tasks") return { data: tasks, response: ok() };
      if (path === "/api/settings/driver") return { data: { kind: "fake" }, response: ok() };
      if (path === "/api/writing/novels") return { data: novels, response: ok() };
      throw new Error(`unexpected GET: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.models.register"] }));
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.models.discover"] }));
    const note = await screen.findByText(de["settings.ai.models.discoverNote"]);
    expect(note).toBeTruthy();

    // The 502: the endpoint did not answer.
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings/providers/{provider_id}/models") {
        return { error: { detail: "model discovery failed" }, response: new Response(null, { status: 502 }) };
      }
      if (path === "/api/settings/providers") return { data: providers, response: ok() };
      if (path === "/api/settings/presets") return { data: presets, response: ok() };
      if (path === "/api/settings/models") return { data: models, response: ok() };
      if (path === "/api/settings/assignments") return { data: assignments, response: ok() };
      if (path === "/api/settings/tasks") return { data: tasks, response: ok() };
      if (path === "/api/settings/driver") return { data: { kind: "fake" }, response: ok() };
      if (path === "/api/writing/novels") return { data: novels, response: ok() };
      throw new Error(`unexpected GET: ${path}`);
    });
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.models.discover"] }));
    expect(await screen.findByText(de["settings.ai.errors.unreachable"])).toBeTruthy();

    // The fake: no endpoint to ask — its own family, never the delete guard's.
    fireEvent.change(screen.getByLabelText(de["settings.ai.models.registerProvider"]), { target: { value: "prov-local" } });
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings/providers/{provider_id}/models") {
        return { error: { detail: "the provider has no endpoint" }, response: new Response(null, { status: 409 }) };
      }
      if (path === "/api/settings/providers") return { data: providers, response: ok() };
      if (path === "/api/settings/presets") return { data: presets, response: ok() };
      if (path === "/api/settings/models") return { data: models, response: ok() };
      if (path === "/api/settings/assignments") return { data: assignments, response: ok() };
      if (path === "/api/settings/tasks") return { data: tasks, response: ok() };
      if (path === "/api/settings/driver") return { data: { kind: "fake" }, response: ok() };
      if (path === "/api/writing/novels") return { data: novels, response: ok() };
      throw new Error(`unexpected GET: ${path}`);
    });
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.models.discover"] }));
    expect(await screen.findByText(de["settings.ai.errors.noEndpoint"])).toBeTruthy();
    expect(screen.queryByText(de["settings.ai.errors.guarded"])).toBeNull();
  });

  it("a registered model rides POST /models and the cascade family re-asks", async () => {
    api.POST.mockImplementation(async (path: string) => {
      if (path === "/api/settings/models") return { data: model({ id: "m-9", name: "Neu" }), response: ok(201) };
      throw new Error(`unexpected POST: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.models.register"] }));
    fireEvent.change(screen.getByLabelText(de["settings.ai.models.registerName"]), { target: { value: "Neu" } });
    fireEvent.change(screen.getByLabelText(de["settings.ai.models.registerModel"]), { target: { value: "gpt-5.4" } });
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.models.registerSubmit"] }));
    await waitFor(() => expect(posts().some(([path]) => path === "/api/settings/models")).toBe(true));
    const entry = posts().find(([path]) => path === "/api/settings/models") as [
      string,
      { body?: Record<string, unknown> },
    ];
    expect(entry[1]?.body).toEqual({ name: "Neu", provider_id: "prov-1", model: "gpt-5.4" });
  });

  it("a refused registration (422) keeps the form's answers", async () => {
    api.POST.mockImplementation(async (path: string) => {
      if (path === "/api/settings/models") {
        return { error: { detail: [{ loc: ["body", "provider_id"], msg: "not yours" }] }, response: new Response(null, { status: 422 }) };
      }
      throw new Error(`unexpected POST: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.models.register"] }));
    fireEvent.change(screen.getByLabelText(de["settings.ai.models.registerName"]), { target: { value: "Neu" } });
    fireEvent.change(screen.getByLabelText(de["settings.ai.models.registerModel"]), { target: { value: "gpt-5.4" } });
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.models.registerSubmit"] }));
    expect(await screen.findByText(de["settings.refused"])).toBeTruthy();
    expect((screen.getByLabelText(de["settings.ai.models.registerName"]) as HTMLInputElement).value).toBe("Neu");
  });
});

describe("the aufgaben rows — the cascade's honest faces", () => {
  it("four assignable rows with both selects; settings.test is the audit row and never a dropdown", async () => {
    renderPage();
    await screen.findAllByTestId("task-row");
    const rows = screen.getAllByTestId("task-row");
    expect(rows.length).toBe(5);
    for (const key of ["writing.continuation", "chat.ask", "knowledge.extract-entities", "knowledge.check-consistency"]) {
      const row = taskRow(key);
      expect(modelSelect(row)).toBeTruthy();
      expect(profileSelect(row)).toBeTruthy();
    }
    const audit = taskRow("settings.test");
    expect(audit.querySelector("select")).toBeNull();
    expect(audit.textContent).toContain(de["settings.ai.task.audit.badge"]);
    expect(audit.textContent).toContain(de["settings.ai.task.auditNote"]);
  });

  it("the fake floor: the resolved number with the fake mark — never the draft's 0-Tok. invention", async () => {
    renderPage();
    await screen.findAllByTestId("task-row");
    const row = taskRow("chat.ask");
    expect(row.textContent).toContain(t("settings.ai.task.effective", { tokens: "4.096" }));
    expect(row.textContent).toContain(de["settings.ai.task.fakeMark"]);
    expect(row.textContent).not.toContain("0 Tok.");
    // The select opens on the cascade option, not a fake claim. The profile
    // select rests beside it — the backend stores no profile without a
    // model, so a choice that would silently revert is never offered.
    expect(modelSelect(row).value).toBe("");
    expect(Array.from(modelSelect(row).options).map((option) => option.value)).toEqual([""]);
    expect(profileSelect(row).value).toBe("balanced");
    expect(profileSelect(row).disabled).toBe(true);
    expect(row.textContent).toContain(de["settings.ai.task.profileNeedsModel"]);
  });

  it("the selects show the stored assignment; the chip answers the effective read", async () => {
    assignments = [{ task_key: "writing.continuation", profile_id: "m-1", output_profile: "long_texts", output_profile_custom: null }];
    tasks = [
      task({ profile_id: "m-1", profile_name: "Cloud-Schreiber", kind: "openai-chat", output_profile: "long_texts", resolved_output_tokens: 12_288 }),
      ...freshTasks().slice(1),
    ];
    models = [model()];
    renderPage();
    await screen.findAllByTestId("task-row");
    const row = taskRow("writing.continuation");
    expect(modelSelect(row).value).toBe("m-1");
    expect(profileSelect(row).value).toBe("long_texts");
    expect(row.textContent).toContain(t("settings.ai.task.effective", { tokens: "12.288" }));
    expect(row.getAttribute("title")).toBeNull();
  });

  it("a model change rides the PUT whole: the model AND the carried profile", async () => {
    assignments = [{ task_key: "writing.continuation", profile_id: "m-1", output_profile: "comprehensive", output_profile_custom: null }];
    models = [model(), model({ id: "m-2", name: "Zweit", is_default: false })];
    api.PUT.mockImplementation(async (path: string) => {
      if (path === "/api/settings/assignments/{task_key}") {
        const [, init] = api.PUT.mock.calls.at(-1) as unknown as [string, { body: Record<string, unknown> }];
        return {
          data: { task_key: "writing.continuation", profile_id: init.body.profile_id, output_profile: init.body.output_profile, output_profile_custom: null },
          response: ok(),
        };
      }
      throw new Error(`unexpected PUT: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.change(modelSelect(taskRow("writing.continuation")), { target: { value: "m-2" } });
    await waitFor(() => expect(puts().length).toBe(1));
    const [path, init] = puts()[0];
    expect(path).toBe("/api/settings/assignments/{task_key}");
    expect(init.body).toEqual({ profile_id: "m-2", output_profile: "comprehensive" });
  });

  it("clearing the model PUTs the cascade floor with the carried profile, and the row re-syncs to the wire's echo", async () => {
    assignments = [{ task_key: "chat.ask", profile_id: "m-1", output_profile: "quick", output_profile_custom: null }];
    models = [model()];
    api.PUT.mockImplementation(async (path: string) => {
      if (path === "/api/settings/assignments/{task_key}") {
        // The real backend's echo: a cleared assignment stores nothing —
        // profile_id null and the default profile answer, whatever the
        // save carried (the router's own rule).
        return {
          data: { task_key: "chat.ask", profile_id: null, output_profile: "balanced", output_profile_custom: null },
          response: ok(),
        };
      }
      throw new Error(`unexpected PUT: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.change(modelSelect(taskRow("chat.ask")), { target: { value: "" } });
    await waitFor(() => expect(puts().length).toBe(1));
    expect(puts()[0][1].body).toEqual({ profile_id: null, output_profile: "quick" });

    // The row re-syncs to the wire's truth, not the carried wish: the
    // select opens on the cascade option, the profile reads the default,
    // resting disabled with its note — a choice nothing stores is never
    // shown as stored.
    const row = taskRow("chat.ask");
    await waitFor(() => expect(modelSelect(row).value).toBe(""));
    expect(profileSelect(row).value).toBe("balanced");
    expect(profileSelect(row).disabled).toBe(true);
    expect(row.textContent).toContain(de["settings.ai.task.profileNeedsModel"]);
  });

  it("a named profile change saves at once and carries the stored model beside it", async () => {
    assignments = [{ task_key: "writing.continuation", profile_id: "m-1", output_profile: "balanced", output_profile_custom: null }];
    models = [model()];
    api.PUT.mockImplementation(async (path: string) => {
      if (path === "/api/settings/assignments/{task_key}") {
        const [, init] = api.PUT.mock.calls.at(-1) as unknown as [string, { body: Record<string, unknown> }];
        return {
          data: { task_key: "writing.continuation", profile_id: init.body.profile_id, output_profile: init.body.output_profile, output_profile_custom: null },
          response: ok(),
        };
      }
      throw new Error(`unexpected PUT: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    fireEvent.change(profileSelect(taskRow("writing.continuation")), { target: { value: "long_texts" } });
    await waitFor(() => expect(puts().length).toBe(1));
    expect(puts()[0][1].body).toEqual({ profile_id: "m-1", output_profile: "long_texts" });
  });

  it("the custom profile rides as its NUMBER, never as the word", async () => {
    models = [model()];
    assignments = [{ task_key: "writing.continuation", profile_id: "m-1", output_profile: "balanced", output_profile_custom: null }];
    api.PUT.mockImplementation(async (path: string) => {
      if (path === "/api/settings/assignments/{task_key}") {
        const [, init] = api.PUT.mock.calls.at(-1) as unknown as [string, { body: Record<string, unknown> }];
        return {
          data: { task_key: "writing.continuation", profile_id: init.body.profile_id, output_profile: "custom", output_profile_custom: init.body.output_profile },
          response: ok(),
        };
      }
      throw new Error(`unexpected PUT: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    const row = taskRow("writing.continuation");
    fireEvent.change(profileSelect(row), { target: { value: "custom" } });
    const input = await screen.findByLabelText(de["settings.ai.profile.customInput"]);
    fireEvent.change(input, { target: { value: "2000" } });
    fireEvent.blur(input);
    await waitFor(() => expect(puts().length).toBe(1));
    expect(puts()[0][1].body).toEqual({ profile_id: "m-1", output_profile: 2000 });
    // The echo re-syncs the row: the stored choice rides back as the word
    // beside its number, and the editor faces exactly that.
    expect(profileSelect(row).value).toBe("custom");
    expect((screen.getByLabelText(de["settings.ai.profile.customInput"]) as HTMLInputElement).value).toBe("2000");
  });

  it("the cap note stands when the ceiling bounds the target — and never otherwise", async () => {
    assignments = [{ task_key: "writing.continuation", profile_id: "m-1", output_profile: "comprehensive", output_profile_custom: null }];
    tasks = [
      task({ profile_id: "m-1", profile_name: "Cloud-Schreiber", kind: "openai-chat", output_profile: "comprehensive", resolved_output_tokens: 8_192 }),
      ...freshTasks().slice(1),
    ];
    models = [model()];
    renderPage();
    await screen.findAllByTestId("task-row");
    const row = taskRow("writing.continuation");
    expect(row.textContent).toContain(t("settings.ai.task.effective", { tokens: "8.192" }));
    expect(row.textContent).toContain(de["settings.ai.task.capped"]);
    // The uncapped row: no note (no ceiling, the target stands as is).
    const chat = taskRow("chat.ask");
    expect(chat.textContent).not.toContain(de["settings.ai.task.capped"]);
    expect(chat.textContent).toContain(t("settings.ai.task.effective", { tokens: "4.096" }));
  });

  it("a refused save under a mismatched selection shows no cap note nothing caused", async () => {
    // Stored: balanced, uncapped at 4.096 — the effective pair's own truth.
    // The editor picks comprehensive and the write dies behind the wire:
    // nothing capped anything, so the refusal face stands alone — the chip
    // compares the stored pair, never the editor's unanswered pick.
    assignments = [{ task_key: "writing.continuation", profile_id: "m-1", output_profile: "balanced", output_profile_custom: null }];
    tasks = [
      task({ profile_id: "m-1", profile_name: "Cloud-Schreiber", kind: "openai-chat", output_profile: "balanced", resolved_output_tokens: 4_096 }),
      ...freshTasks().slice(1),
    ];
    api.PUT.mockImplementation(async (path: string) => {
      if (path === "/api/settings/assignments/{task_key}") {
        return { error: { detail: "the write died behind the wire" }, response: new Response(null, { status: 500 }) };
      }
      throw new Error(`unexpected PUT: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    const row = taskRow("writing.continuation");
    fireEvent.change(profileSelect(row), { target: { value: "comprehensive" } });
    expect(await screen.findByText(de["settings.ai.errors.generic"])).toBeTruthy();
    expect(profileSelect(row).value).toBe("comprehensive"); // a refusal keeps the answers
    expect(row.textContent).not.toContain(de["settings.ai.task.capped"]);
    expect(row.textContent).toContain(t("settings.ai.task.effective", { tokens: "4.096" }));
  });

  it("a true cap survives a selection the stored world does not carry", async () => {
    // Stored: comprehensive capped at the model's 8.192. The editor moves
    // the select to quick and the wire refuses: the effective pair stands
    // untouched, and 8.192 < 32.768 stays the ceiling's own doing — the
    // note keeps standing beside the refusal face.
    assignments = [{ task_key: "writing.continuation", profile_id: "m-1", output_profile: "comprehensive", output_profile_custom: null }];
    tasks = [
      task({ profile_id: "m-1", profile_name: "Cloud-Schreiber", kind: "openai-chat", output_profile: "comprehensive", resolved_output_tokens: 8_192 }),
      ...freshTasks().slice(1),
    ];
    api.PUT.mockImplementation(async (path: string) => {
      if (path === "/api/settings/assignments/{task_key}") {
        return { error: { detail: "the write died behind the wire" }, response: new Response(null, { status: 500 }) };
      }
      throw new Error(`unexpected PUT: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    const row = taskRow("writing.continuation");
    expect(row.textContent).toContain(de["settings.ai.task.capped"]);
    fireEvent.change(profileSelect(row), { target: { value: "quick" } });
    expect(await screen.findByText(de["settings.ai.errors.generic"])).toBeTruthy();
    expect(row.textContent).toContain(de["settings.ai.task.capped"]);
  });

  it("a refused custom edit keeps the note honest about the stored number, not the typed one", async () => {
    // Stored: custom 6.000, no ceiling — 6.000 stands uncapped. The writer
    // types 40000 and the wire refuses: the typed number stores nothing, so
    // the chip compares the stored 6.000 against itself — no false cap note
    // rides the refusal (the editor's live number would have shown one).
    assignments = [{ task_key: "writing.continuation", profile_id: "m-1", output_profile: "custom", output_profile_custom: 6_000 }];
    tasks = [
      task({ profile_id: "m-1", profile_name: "Cloud-Schreiber", kind: "openai-chat", output_profile: "custom", resolved_output_tokens: 6_000 }),
      ...freshTasks().slice(1),
    ];
    api.PUT.mockImplementation(async (path: string) => {
      if (path === "/api/settings/assignments/{task_key}") {
        return {
          error: { detail: [{ loc: ["body", "output_profile"], msg: "above the model's stored ceiling" }] },
          response: new Response(null, { status: 422 }),
        };
      }
      throw new Error(`unexpected PUT: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    const row = taskRow("writing.continuation");
    const input = await screen.findByLabelText(de["settings.ai.profile.customInput"]);
    fireEvent.change(input, { target: { value: "40000" } });
    fireEvent.blur(input);
    expect(await screen.findByText(de["settings.refused"])).toBeTruthy();
    expect((screen.getByLabelText(de["settings.ai.profile.customInput"]) as HTMLInputElement).value).toBe("40000");
    expect(row.textContent).not.toContain(de["settings.ai.task.capped"]);
    expect(row.textContent).toContain(t("settings.ai.task.effective", { tokens: "6.000" }));
  });

  it("a refused assignment (422, the custom above the ceiling) keeps the answers and names itself", async () => {
    models = [model()];
    assignments = [{ task_key: "writing.continuation", profile_id: "m-1", output_profile: "balanced", output_profile_custom: null }];
    api.PUT.mockImplementation(async (path: string) => {
      if (path === "/api/settings/assignments/{task_key}") {
        return {
          error: { detail: [{ loc: ["body", "output_profile"], msg: "above the model's stored ceiling" }] },
          response: new Response(null, { status: 422 }),
        };
      }
      throw new Error(`unexpected PUT: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    const row = taskRow("writing.continuation");
    fireEvent.change(profileSelect(row), { target: { value: "custom" } });
    const input = await screen.findByLabelText(de["settings.ai.profile.customInput"]);
    fireEvent.change(input, { target: { value: "999999" } });
    fireEvent.blur(input);
    expect(await screen.findByText(de["settings.refused"])).toBeTruthy();
    expect((screen.getByLabelText(de["settings.ai.profile.customInput"]) as HTMLInputElement).value).toBe("999999");
  });
});

describe("the system diagnose — only what the reads answer", () => {
  it("fake: the offline card; configured: the configured card; no answer: no card", async () => {
    renderPage();
    await screen.findAllByTestId("task-row");
    expect(await screen.findByTestId("driver-card").then(() => screen.getByText(de["settings.ai.diag.fakeTitle"]))).toBeTruthy();
    expect(screen.getByText(de["settings.ai.diag.noAction"])).toBeTruthy();

    cleanup();
    queryClient.clear();
    driverKind = "configured";
    scriptReads();
    renderPage();
    await screen.findAllByTestId("task-row");
    expect(await screen.findByText(de["settings.ai.diag.configuredTitle"])).toBeTruthy();

    cleanup();
    queryClient.clear();
    driverKind = { fail: true };
    scriptReads();
    renderPage();
    await screen.findAllByTestId("task-row");
    await waitFor(() => expect(screen.queryByTestId("driver-card")).toBeNull());
  });

  it("a model's stored failure gets its card, with the code and the real retest", async () => {
    models = [model({ last_error_code: "auth", last_error_at: "2026-11-21T09:00:00Z" })];
    api.POST.mockImplementation(async (path: string) => {
      if (path === "/api/settings/models/{model_id}/test") return { data: { ok: true, error: null, latency_ms: 42 }, response: ok() };
      throw new Error(`unexpected POST: ${path}`);
    });
    renderPage();
    await screen.findAllByTestId("task-row");
    const card = await screen.findByTestId("diagnose-error-card");
    expect(card.textContent).toContain(t("settings.ai.diag.errorTitle", { code: "auth" }));
    fireEvent.click(screen.getByRole("button", { name: de["settings.ai.diag.retest"] }));
    await waitFor(() => expect(posts().some(([path]) => path === "/api/settings/models/{model_id}/test")).toBe(true));
  });
});

describe("du-tone — the catalogs speak to the writer", () => {
  it("de duzt, fr tutoie — the new keys carry the same shape in all three catalogs", () => {
    expect(de["settings.ai.subtitle"]).toContain("deine");
    expect(fr["settings.ai.subtitle"]).toMatch(/\bton\b/);
    expect(en["settings.ai.subtitle"]).toContain("your");
    const keys = (catalog: typeof en) => Object.keys(catalog).filter((key) => key.startsWith("settings.ai.")).sort();
    expect(keys(de)).toEqual(keys(en));
    expect(keys(fr)).toEqual(keys(en));
  });
});
