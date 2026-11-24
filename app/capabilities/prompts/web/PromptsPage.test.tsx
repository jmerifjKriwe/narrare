// @vitest-environment jsdom
/**
 * The prompts surface (W8 Task 12) — the settings area's third page, driven
 * over a bare router with the API client mocked at its module boundary; the
 * queries and the query client are real. The live test's wire is `fetch` +
 * SSE (the writing continuation's transport), so that seam is stubbed on
 * `globalThis.fetch`.
 *
 * The pins hold the honest-state rules and the draft's authority: the
 * catalog's override marks on their real fields, the novel filter composing,
 * the editor's scope chips (the novel chip only where scopable), the
 * preview's POST round-trip with/without the draft (the browser-callable
 * seam Task 11 moved to POST), the contract diagnostic's three faces, the
 * 422 refusal family in its exact copy, and the live test whose warning
 * precedes the call — the SSE stream rendered live with the fake driver's
 * honest mark, the coded faces localized by code.
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
import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { PromptsPage } from "./PromptsPage";

const de = catalogs.de;
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

configure({ asyncUtilTimeout: 15_000 });
vi.setConfig({ testTimeout: 25_000 });

const NOVEL_A = { id: "novel-1", title: "Dead Signal", genre: null, archived_at: null, updated_at: "2026-11-20T10:00:00Z" };
const NOVEL_B = { id: "novel-2", title: "Im Stillen Wald", genre: null, archived_at: null, updated_at: "2026-11-19T10:00:00Z" };

const BUNDLED =
  "# System-Direktive: Ghost-Writing\nDu bist ein literarischer Ghost-Writing-Assistent.\nKapitel: {{chapter_title}}\nManuskript-Ende:\n{{tail}}\n";

const VARIABLES = [
  { name: "chapter_title", example: "Kapitel 2 — Nevada Echoes" },
  { name: "tail", example: "Fließtext-Puffer" },
];

function summary(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    key: "writing.continuation",
    novel_scopable: true,
    override_global: false,
    override_novel: false,
    bundled_summary: "Ghost-Writing & dynamische Satzfortführung im Manuskript.",
    ...overrides,
  };
}

const baseSummaries = (): Record<string, unknown>[] => [
  summary(),
  summary({ key: "chat.ask", novel_scopable: false, bundled_summary: "Dialogische Befragung der Lore und Manuskript-Zusammenhänge." }),
  summary({ key: "knowledge.extract-entities", bundled_summary: "Erkennt Figuren, Orte, Artefakte und Relationen." }),
  summary({ key: "knowledge.check-consistency", bundled_summary: "Kausalitäts-Audit gegen verankerte Figurenbiografien." }),
];

function detail(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    bundled_content: BUNDLED,
    variables: VARIABLES,
    override: null,
    effective_content: BUNDLED,
    ...overrides,
  };
}

function ok(status = 200): Response {
  return new Response(null, { status });
}

/** The wire's refusal body: FastAPI's HTTPException wraps the gate's
 *  refusal in `detail` — the API pins' shape (`{detail: {reason, detail}}`),
 *  exactly what openapi-fetch hands back as `error`. */
function refused(status: number, reason: string, message: string): { data: null; error: unknown; response: Response } {
  return { data: null, error: { detail: { reason, detail: message } }, response: new Response(null, { status }) };
}

let novelList: Record<string, unknown>[];
let summaries: Record<string, unknown>[];
let details: Record<string, Record<string, unknown>>;
let novelOverridePresent: boolean;

/** A controllable promise for the reset's in-flight network edges. */
function deferred<T>(): { promise: Promise<T>; resolve(value: T): void } {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

/** The mock instance's reads. The list answers per novel_id; the detail per
 *  key and scope — the shapes mirror the wire. */
type GetMock = (
  path: string,
  init?: { params?: { path?: Record<string, string>; query?: Record<string, unknown> } },
) => Promise<unknown>;

function scriptReads(): void {
  api.GET.mockImplementation(async (path: string, init?: { params?: { path?: Record<string, string>; query?: Record<string, unknown> } }) => {
    if (path === "/api/writing/novels") return { data: novelList, response: ok() };
    if (path === "/api/prompts") {
      const novelId = init?.params?.query?.novel_id;
      if (novelId === undefined) return { data: summaries, response: ok() };
      // The novel-scope ask: override_novel answers per the seeded marks.
      return {
        data: summaries.map((row) => ({
          ...row,
          override_novel:
            row.key === "writing.continuation" && novelId === "novel-1" && novelOverridePresent,
        })),
        response: ok(),
      };
    }
    if (path === "/api/prompts/{key}") {
      const key = init?.params?.path?.key ?? "";
      const row = details[key];
      if (row === undefined) return { data: null, error: { detail: "no bundled prompt carries this key" }, response: new Response(null, { status: 404 }) };
      return { data: row, response: ok() };
    }
    if (path === "/api/prompts/{key}/diff") {
      const key = init?.params?.path?.key ?? "";
      const row = details[key] ?? detail();
      return {
        data: { bundled_content: row.bundled_content, override_content: (row.override as { content: string } | null)?.content ?? null },
        response: ok(),
      };
    }
    throw new Error(`unexpected GET: ${path}`);
  });
}

/** The bare test router the page mounts through: the hub chrome reads the
 *  router's own location state (the active face), so the render needs the
 *  router context — the AI-Regeln suite's pattern. */
const testRoot = createRootRoute({ component: () => <Outlet /> });
const promptsRoute = createRoute({
  getParentRoute: () => testRoot,
  path: "/settings/prompts",
  component: PromptsPage,
});
const awayRoute = createRoute({
  getParentRoute: () => testRoot,
  path: "/elsewhere",
  component: () => <div data-testid="away">Elsewhere</div>,
});

function renderPage() {
  const router = createRouter({
    routeTree: testRoot.addChildren([promptsRoute, awayRoute]),
    history: createMemoryHistory({ initialEntries: ["/settings/prompts"] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

/** Wait for the page's ready face: the catalog answered, the editor stood. */
async function readyEditor(): Promise<HTMLElement> {
  const cards = await screen.findAllByTestId("prompt-card");
  expect(cards.length).toBe(4);
  return await screen.findByTestId("prompts-editor");
}

beforeEach(() => {
  applyLocale("de");
  novelList = [NOVEL_A, NOVEL_B];
  summaries = baseSummaries();
  details = { "writing.continuation": detail(), "chat.ask": detail(), "knowledge.extract-entities": detail(), "knowledge.check-consistency": detail() };
  novelOverridePresent = true;
  scriptReads();
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("the catalog with its override marks", () => {
  it("renders the four keys on the global scope, every card on the standard mark", async () => {
    renderPage();
    const cards = await screen.findAllByTestId("prompt-card");
    expect(cards.length).toBe(4);
    const continuation = within(cards[0]!);
    expect(continuation.getByText(de["prompts.key.writing.continuation"])).toBeTruthy();
    expect(continuation.getByText(de["prompts.catalog.globalStandard"])).toBeTruthy();
    // The global-only key carries its scope fact beside the mark.
    const chat = within(cards[1]!);
    expect(chat.getByText(de["prompts.catalog.globalStandard"])).toBeTruthy();
    expect(chat.getByText(de["prompts.catalog.globalOnly"])).toBeTruthy();
    // No novel badge on the global scope.
    expect(screen.queryByTestId("override-badge")).toBeNull();
  });

  it("a global override flips the mark on its key", async () => {
    summaries = [summary({ override_global: true }), ...baseSummaries().slice(1)];
    scriptReads();
    renderPage();
    const cards = await screen.findAllByTestId("prompt-card");
    expect(within(cards[0]!).getByText(de["prompts.catalog.globalOverride"])).toBeTruthy();
    expect(within(cards[1]!).getByText(de["prompts.catalog.globalStandard"])).toBeTruthy();
  });

  it("the novel filter composes: the list re-asks with the novel, the inherits mark and the badge stand", async () => {
    renderPage();
    await readyEditor();
    const select = screen.getByTestId("scope-select").querySelector("select") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "novel-1" } });
    await waitFor(() => expect(api.GET).toHaveBeenCalledWith("/api/prompts", expect.objectContaining({
      params: expect.objectContaining({ query: { novel_id: "novel-1" } }),
    })));
    const cards = await screen.findAllByTestId("prompt-card");
    expect(within(cards[0]!).getByText(de["prompts.catalog.novelOverride"].replace("{novel}", "Dead Signal"))).toBeTruthy();
    expect(within(cards[1]!).getByText(de["prompts.catalog.globalOnly"])).toBeTruthy();
    const badge = screen.getByTestId("override-badge");
    expect(badge.textContent).toContain("1 roman-spezifischer Override aktiv");
    // Back to global: the badge goes, the global marks answer.
    fireEvent.change(select, { target: { value: "" } });
    await waitFor(() => expect(screen.queryByTestId("override-badge")).toBeNull());
  });
});

describe("the editor's scope chips", () => {
  it("mounts on the first key with the effective text and the variable legend", async () => {
    renderPage();
    const editor = await readyEditor();
    const textarea = within(editor).getByTestId("draft-textarea") as HTMLTextAreaElement;
    expect(textarea.value).toBe(BUNDLED);
    const legend = within(editor).getByTestId("variables-legend");
    expect(legend.textContent).toContain("chapter_title");
    expect(legend.textContent).toContain("tail");
    expect(within(editor).getByText(de["prompts.key.writing.continuation.desc"])).toBeTruthy();
  });

  it("with a novel selected the novel chip stands and rides the novel scope; a chip switch re-asks", async () => {
    renderPage();
    await readyEditor();
    const select = screen.getByTestId("scope-select").querySelector("select") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "novel-1" } });
    const editor = await screen.findByTestId("prompts-editor");
    const novelChip = within(editor).getByTestId("scope-chip-novel");
    expect(novelChip.textContent).toContain("Dieser Roman: Dead Signal");
    // The novel tier is the default editing scope: the detail re-asks with
    // the novel id.
    await waitFor(() => expect(api.GET).toHaveBeenCalledWith("/api/prompts/{key}", expect.objectContaining({
      params: expect.objectContaining({ path: { key: "writing.continuation" }, query: { novel_id: "novel-1" } }),
    })));
    // The chip switch flips the detail's scope ask.
    fireEvent.click(within(editor).getByTestId("scope-chip-global"));
    await waitFor(() => expect(api.GET).toHaveBeenCalledWith("/api/prompts/{key}", expect.objectContaining({
      params: expect.objectContaining({ path: { key: "writing.continuation" }, query: {} }),
    })));
  });

  it("the global-only key wears the Global chip alone, on the global scope", async () => {
    renderPage();
    await readyEditor();
    const cards = await screen.findAllByTestId("prompt-card");
    fireEvent.click(cards[1]!);
    const editor = await screen.findByTestId("prompts-editor");
    expect(within(editor).queryByTestId("scope-chip-novel")).toBeNull();
    expect(within(editor).getByTestId("scope-chip-global")).toBeTruthy();
    // Even with a novel filtered, chat.ask stays on the global scope.
    const select = screen.getByTestId("scope-select").querySelector("select") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "novel-1" } });
    await waitFor(() => expect(api.GET).toHaveBeenCalledWith("/api/prompts/{key}", expect.objectContaining({
      params: expect.objectContaining({ path: { key: "chat.ask" }, query: {} }),
    })));
  });
});

describe("the preview", () => {
  function previewAnswer(overrides: Record<string, unknown> = {}): Record<string, unknown> {
    return {
      rendered: "Gerenderter Text mit gefülltem Tail.",
      variables: [
        { name: "chapter_title", value: "Kapitel 2 — Nevada Echoes", used: true },
        { name: "tail", value: "Fließtext-Puffer", used: false },
      ],
      diagnostics: { chars: 842, lines: 18, contract_ok: true },
      ...overrides,
    };
  }

  it("the pristine draft previews the saved effective: POST without a body", async () => {
    api.POST.mockResolvedValue({ data: previewAnswer(), response: ok() });
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("preview-button"));
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith("/api/prompts/{key}/preview", expect.objectContaining({
      params: expect.objectContaining({ path: { key: "writing.continuation" }, query: {} }),
      body: undefined,
    })));
    const card = await screen.findByTestId("preview-card");
    expect(within(card).getByTestId("preview-rendered").textContent).toContain("Gerenderter Text mit gefülltem Tail.");
    expect(within(card).getByText(de["prompts.preview.diagnostics"])).toBeTruthy();
    expect(within(card).getByText(de["prompts.preview.chars"].replace("{count}", "842"))).toBeTruthy();
    expect(within(card).getByText(de["prompts.preview.lines"].replace("{count}", "18"))).toBeTruthy();
    expect(within(card).getByText(de["prompts.preview.contractOk"])).toBeTruthy();
    expect(within(card).getByText(de["prompts.preview.used"])).toBeTruthy();
    expect(within(card).getByText(de["prompts.preview.unused"])).toBeTruthy();
  });

  it("a dirty draft rides the POST body and the novel query", async () => {
    api.POST.mockResolvedValue({ data: previewAnswer(), response: ok() });
    renderPage();
    await readyEditor();
    const select = screen.getByTestId("scope-select").querySelector("select") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "novel-1" } });
    const novelEditor = await screen.findByTestId("prompts-editor");
    const textarea = within(novelEditor).getByTestId("draft-textarea") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "# Mein Entwurf\n{{tail}}" } });
    fireEvent.click(within(novelEditor).getByTestId("preview-button"));
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith("/api/prompts/{key}/preview", expect.objectContaining({
      params: expect.objectContaining({ path: { key: "writing.continuation" }, query: { novel_id: "novel-1" } }),
      body: { content: "# Mein Entwurf\n{{tail}}" },
    })));
  });

  it("a contract failure stands beside the text as its own face", async () => {
    api.POST.mockResolvedValue({
      data: previewAnswer({ diagnostics: { chars: 100, lines: 4, contract_ok: false } }),
      response: ok(),
    });
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("preview-button"));
    const card = await screen.findByTestId("preview-card");
    expect(within(card).getByTestId("preview-contract-fail").textContent).toBe(de["prompts.preview.contractFail"]);
  });

  it("a key without a contract says so", async () => {
    api.POST.mockResolvedValue({
      data: previewAnswer({ diagnostics: { chars: 100, lines: 4, contract_ok: null } }),
      response: ok(),
    });
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("preview-button"));
    const card = await screen.findByTestId("preview-card");
    expect(within(card).getByText(de["prompts.preview.contractNone"])).toBeTruthy();
  });

  it("a refused draft shows the refusal family", async () => {
    api.POST.mockResolvedValue(refused(422, "syntax", "unexpected 'endif' at line 3"));
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("preview-button"));
    const face = await screen.findByTestId("refusal-face");
    expect(face.textContent).toContain(de["prompts.refusal.headline"].replace("{reason}", de["prompts.refusal.reason.syntax"]));
    expect(face.textContent).toContain("unexpected 'endif' at line 3");
  });

  it("names its busy face while the render stands", async () => {
    api.POST.mockImplementation(() => new Promise(() => {}));
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("preview-button"));
    expect(await screen.findByText(de["prompts.preview.busy"])).toBeTruthy();
  });
});

describe("the save gate's refusal family", () => {
  async function saveDraft(): Promise<void> {
    const editor = await readyEditor();
    const textarea = within(editor).getByTestId("draft-textarea") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "# Umgestimmt\n{{tail}}" } });
    fireEvent.click(within(editor).getByTestId("save-button"));
  }

  it("saves the draft to the editor's scope and flips the page to the saved face", async () => {
    api.PUT.mockResolvedValue({ data: detail({ override: { scope: "global", content: "# Umgestimmt\n{{tail}}" } }), response: ok() });
    renderPage();
    await saveDraft();
    await waitFor(() => expect(api.PUT).toHaveBeenCalledWith("/api/prompts/{key}", expect.objectContaining({
      params: expect.objectContaining({ path: { key: "writing.continuation" } }),
      body: { content: "# Umgestimmt\n{{tail}}", novel_id: null },
    })));
    expect(await screen.findByTestId("saved-face")).toBeTruthy();
    // The family re-asks: the list's mark moves with the landed write.
    await waitFor(() => expect(api.GET).toHaveBeenCalledWith("/api/prompts", expect.anything()));
  });

  it("keystrokes between the save-click and the landing refetch are never clobbered", async () => {
    // The save lands, the invalidation refetch answers with the saved
    // override — the baseline's BYTES change under the cursor. The draft
    // belongs to its author: the keystroke typed while the save was in
    // flight survives, the draft is not reset to the new baseline.
    const SAVED = "# Umgestimmt\n{{tail}}";
    let landed = false;
    api.PUT.mockImplementation(async () => {
      landed = true;
      return { data: detail({ override: { scope: "global", content: SAVED } }), response: ok() };
    });
    renderPage();
    const editor = await readyEditor();
    const textarea = within(editor).getByTestId("draft-textarea") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: SAVED } });
    fireEvent.click(within(editor).getByTestId("save-button"));
    // The keystroke rides the in-flight save.
    fireEvent.change(textarea, { target: { value: `${SAVED} und ein Nachsatz.` } });
    expect(await screen.findByTestId("saved-face")).toBeTruthy();
    // The refetch landed (the detail now carries the override).
    await waitFor(() => expect(landed && api.GET.mock.calls.some(([path]) => path === "/api/prompts/{key}")).toBe(true));
    expect((screen.getByTestId("draft-textarea") as HTMLTextAreaElement).value).toBe(`${SAVED} und ein Nachsatz.`);
  });

  it("the novel scope rides the novel id", async () => {
    api.PUT.mockResolvedValue({ data: detail(), response: ok() });
    renderPage();
    await readyEditor();
    const select = screen.getByTestId("scope-select").querySelector("select") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "novel-1" } });
    const novelEditor = await screen.findByTestId("prompts-editor");
    const textarea = within(novelEditor).getByTestId("draft-textarea") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "# Roman-Override\n{{tail}}" } });
    fireEvent.click(within(novelEditor).getByTestId("save-button"));
    await waitFor(() => expect(api.PUT).toHaveBeenCalledWith("/api/prompts/{key}", expect.objectContaining({
      body: { content: "# Roman-Override\n{{tail}}", novel_id: "novel-1" },
    })));
  });

  it.each([
    ["syntax", "Syntax"],
    ["undefined-variable", "Unbekannte Variable"],
    ["include-cycle", "Include-Zyklus"],
    ["contract", "Fehlender Marker"],
    ["novel-scope", "Scope-Regel"],
  ])("the %s refusal carries its exact copy family", async (reason, label) => {
    api.PUT.mockResolvedValue(refused(422, reason, "die ehrliche Detail-Sentence des Backends"));
    renderPage();
    await saveDraft();
    const face = await screen.findByTestId("refusal-face");
    expect(face.textContent).toContain(de["prompts.refusal.headline"].replace("{reason}", de[`prompts.refusal.reason.${reason}` as keyof typeof de]));
    expect(face.textContent).toContain(label);
    expect(face.textContent).toContain("die ehrliche Detail-Sentence des Backends");
  });

  it("the framework's own 422 and every other failure answer generically, the draft kept", async () => {
    api.PUT.mockResolvedValue({ data: null, error: { detail: [{ loc: ["body"], msg: "bad", type: "value_error" }] }, response: new Response(null, { status: 422 }) });
    renderPage();
    await saveDraft();
    const face = await screen.findByTestId("refusal-face");
    expect(face.textContent).toContain(de["prompts.errors.generic"]);
    const textarea = screen.getByTestId("draft-textarea") as HTMLTextAreaElement;
    expect(textarea.value).toBe("# Umgestimmt\n{{tail}}");
  });
});

describe("the reset", () => {
  it("asks once, then deletes the novel override and re-asks the family", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: new Response(null, { status: 204 }) });
    renderPage();
    await readyEditor();
    const select = screen.getByTestId("scope-select").querySelector("select") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "novel-1" } });
    const editor = await screen.findByTestId("prompts-editor");
    fireEvent.click(within(editor).getByTestId("reset-button"));
    // The one-time confirmation stands first; no delete has run.
    expect(within(editor).getByTestId("reset-confirm").textContent).toContain(de["prompts.editor.resetConfirm"]);
    expect(api.DELETE).not.toHaveBeenCalled();
    fireEvent.click(within(editor).getByTestId("reset-go"));
    await waitFor(() => expect(api.DELETE).toHaveBeenCalledWith("/api/prompts/{key}", expect.objectContaining({
      params: expect.objectContaining({ path: { key: "writing.continuation" }, query: { novel_id: "novel-1" } }),
    })));
    await waitFor(() => expect(api.GET).toHaveBeenCalledWith("/api/prompts", expect.anything()));
  });

  it("the global tier's reset is the override delete", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: new Response(null, { status: 204 }) });
    renderPage();
    const editor = await readyEditor();
    expect(within(editor).getByTestId("reset-button").textContent).toContain(de["prompts.editor.deleteOverride"]);
    fireEvent.click(within(editor).getByTestId("reset-button"));
    fireEvent.click(within(editor).getByTestId("reset-go"));
    await waitFor(() => expect(api.DELETE).toHaveBeenCalledWith("/api/prompts/{key}", expect.objectContaining({
      params: expect.objectContaining({ path: { key: "writing.continuation" }, query: {} }),
    })));
  });

  it("locks editing and navigation until reset lands the inherited baseline", async () => {
    const OVERRIDE = "# Globaler Override\n{{tail}}";
    const INHERITED = "# Global-Standard\n{{tail}}";
    details["writing.continuation"] = detail({
      override: { scope: "global", content: OVERRIDE },
      effective_content: OVERRIDE,
    });
    summaries = [summary({ override_global: true }), ...baseSummaries().slice(1)];
    const deleted = deferred<{ data: undefined; response: Response }>();
    api.DELETE.mockReturnValue(deleted.promise);

    renderPage();
    const editor = await readyEditor();
    const textarea = within(editor).getByTestId("draft-textarea") as HTMLTextAreaElement;
    expect(textarea.value).toBe(OVERRIDE);
    fireEvent.click(within(editor).getByTestId("reset-button"));
    fireEvent.click(within(editor).getByTestId("reset-go"));
    await waitFor(() => expect(api.DELETE).toHaveBeenCalledTimes(1));

    // Every editing door and both navigation doors are locked while the
    // shared reset mutation is pending. Typing cannot race the deletion.
    expect(textarea.disabled).toBe(true);
    for (const button of within(editor).getByTestId("variables-legend").querySelectorAll("button")) {
      expect((button as HTMLButtonElement).disabled).toBe(true);
    }
    for (const id of ["save-button", "preview-button", "live-button", "reset-button", "scope-chip-global"]) {
      expect((within(editor).getByTestId(id) as HTMLButtonElement).disabled).toBe(true);
    }
    const select = screen.getByTestId("scope-select").querySelector("select") as HTMLSelectElement;
    expect(select.disabled).toBe(true);
    for (const card of screen.getAllByTestId("prompt-card")) {
      expect((card as HTMLButtonElement).disabled).toBe(true);
    }
    fireEvent.change(textarea, { target: { value: "während des Resets getippt" } });
    expect(textarea.value).toBe(OVERRIDE);
    fireEvent.click(screen.getAllByTestId("prompt-card")[1]!);
    fireEvent.change(select, { target: { value: "novel-1" } });
    expect(within(editor).getByTestId("editor-key").textContent).toBe("writing.continuation");

    details["writing.continuation"] = detail({ override: null, effective_content: INHERITED });
    summaries = baseSummaries();
    deleted.resolve({ data: undefined, response: new Response(null, { status: 204 }) });
    await waitFor(() => expect((screen.getByTestId("draft-textarea") as HTMLTextAreaElement).value).toBe(INHERITED));
    expect((screen.getByTestId("draft-textarea") as HTMLTextAreaElement).disabled).toBe(false);
  });

  it("a route remount during the fresh detail read never mounts the deleted draft", async () => {
    const OVERRIDE = "# Globaler Override\n{{tail}}";
    const INHERITED = "# Global-Standard\n{{tail}}";
    details["writing.continuation"] = detail({
      override: { scope: "global", content: OVERRIDE },
      effective_content: OVERRIDE,
    });
    summaries = [summary({ override_global: true }), ...baseSummaries().slice(1)];
    const fresh = deferred<{ data: Record<string, unknown>; response: Response }>();
    const originalGet = api.GET.getMockImplementation()! as GetMock;
    let detailReads = 0;
    api.GET.mockImplementation(async (path: string, init?: { params?: { path?: Record<string, string>; query?: Record<string, unknown> } }) => {
      if (
        path === "/api/prompts/{key}" &&
        init?.params?.path?.key === "writing.continuation" &&
        init?.params?.query?.novel_id === undefined
      ) {
        detailReads += 1;
        if (detailReads > 1) return fresh.promise;
      }
      return originalGet(path, init);
    });
    api.DELETE.mockImplementation(async () => {
      details["writing.continuation"] = detail({ override: null, effective_content: INHERITED });
      summaries = baseSummaries();
      return { data: undefined, response: new Response(null, { status: 204 }) };
    });

    const router = renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("reset-button"));
    fireEvent.click(within(editor).getByTestId("reset-go"));
    await waitFor(() => expect(detailReads).toBe(2));

    // The successful DELETE reset the exact cache entry and its active
    // observer. A remount can only see loading/fresh data, never OVERRIDE.
    expect(queryClient.getQueryData(["prompts", "detail", "writing.continuation", null])).toBeUndefined();
    expect(screen.queryByTestId("prompts-editor")).toBeNull();
    await act(async () => { router.history.push("/elsewhere"); });
    expect(screen.getByTestId("away")).toBeTruthy();
    await act(async () => { router.history.push("/settings/prompts"); });
    expect(screen.queryByTestId("draft-textarea")).toBeNull();
    const remountedSelect = screen.getByTestId("scope-select").querySelector("select") as HTMLSelectElement;
    expect(remountedSelect.disabled).toBe(true);
    for (const card of screen.getAllByTestId("prompt-card")) {
      expect((card as HTMLButtonElement).disabled).toBe(true);
    }

    fresh.resolve({ data: details["writing.continuation"]!, response: ok() });
    await waitFor(() => expect((screen.getByTestId("draft-textarea") as HTMLTextAreaElement).value).toBe(INHERITED));
    // One reset read, not a mutation GET plus an invalidation refetch.
    expect(detailReads).toBe(2);
  });

  it("a route remount before DELETE resolves still follows the shared completion revision", async () => {
    const OVERRIDE = "# Globaler Override\n{{tail}}";
    const INHERITED = "# Global-Standard\n{{tail}}";
    details["writing.continuation"] = detail({
      override: { scope: "global", content: OVERRIDE },
      effective_content: OVERRIDE,
    });
    summaries = [summary({ override_global: true }), ...baseSummaries().slice(1)];
    const deleted = deferred<{ data: undefined; response: Response }>();
    api.DELETE.mockReturnValue(deleted.promise);
    const originalGet = api.GET.getMockImplementation()! as GetMock;
    let deleteCommitted = false;
    let freshDetailReads = 0;
    api.GET.mockImplementation(async (path: string, init?: { params?: { path?: Record<string, string>; query?: Record<string, unknown> } }) => {
      if (
        path === "/api/prompts/{key}" &&
        init?.params?.path?.key === "writing.continuation" &&
        init?.params?.query?.novel_id === undefined &&
        deleteCommitted
      ) {
        freshDetailReads += 1;
      }
      return originalGet(path, init);
    });

    const router = renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("reset-button"));
    fireEvent.click(within(editor).getByTestId("reset-go"));
    await waitFor(() => expect(api.DELETE).toHaveBeenCalledTimes(1));

    // Leave before the DELETE answers. The new page sees the shared pending
    // lock, but its detail cache still holds the not-yet-deleted override.
    await act(async () => { router.history.push("/elsewhere"); });
    await act(async () => { router.history.push("/settings/prompts"); });
    const remountedEditor = await screen.findByTestId("prompts-editor");
    const remountedTextarea = within(remountedEditor).getByTestId("draft-textarea") as HTMLTextAreaElement;
    expect(remountedTextarea.value).toBe(OVERRIDE);
    expect(remountedTextarea.disabled).toBe(true);

    // DELETE commits and the fresh detail answers immediately. The original
    // page's per-call callback is gone; only shared mutation state can revise
    // this remounted editor's identity.
    deleteCommitted = true;
    details["writing.continuation"] = detail({ override: null, effective_content: INHERITED });
    summaries = baseSummaries();
    deleted.resolve({ data: undefined, response: new Response(null, { status: 204 }) });

    await waitFor(() => expect((screen.getByTestId("draft-textarea") as HTMLTextAreaElement).value).toBe(INHERITED));
    expect(remountedTextarea.isConnected).toBe(false);
    expect((screen.getByTestId("draft-textarea") as HTMLTextAreaElement).disabled).toBe(false);
    expect(freshDetailReads).toBe(1);

    // Save now carries the inherited baseline, never the deleted override.
    api.PUT.mockResolvedValue({ data: details["writing.continuation"], response: ok() });
    fireEvent.click(screen.getByTestId("save-button"));
    await waitFor(() => expect(api.PUT).toHaveBeenCalledWith("/api/prompts/{key}", expect.objectContaining({
      body: { content: INHERITED, novel_id: null },
    })));
  });

  it("a global reset refreshes cached inheriting novel details", async () => {
    const OVERRIDE = "# Globaler Override\n{{tail}}";
    const INHERITED = "# Global-Standard\n{{tail}}";
    details["writing.continuation"] = detail({
      override: { scope: "global", content: OVERRIDE },
      effective_content: OVERRIDE,
    });
    summaries = [summary({ override_global: true }), ...baseSummaries().slice(1)];
    const originalGet = api.GET.getMockImplementation()! as GetMock;
    let globalDeleted = false;
    let novelDetailReads = 0;
    api.GET.mockImplementation(async (path: string, init?: { params?: { path?: Record<string, string>; query?: Record<string, unknown> } }) => {
      if (path === "/api/prompts/{key}" && init?.params?.path?.key === "writing.continuation" && init?.params?.query?.novel_id === "novel-1") {
        novelDetailReads += 1;
        const row = globalDeleted
          ? details["writing.continuation"]!
          : detail({ override: null, effective_content: OVERRIDE });
        return { data: row, response: ok() };
      }
      return originalGet(path, init);
    });
    api.DELETE.mockImplementation(async () => {
      globalDeleted = true;
      details["writing.continuation"] = detail({ override: null, effective_content: INHERITED });
      summaries = baseSummaries();
      return { data: undefined, response: new Response(null, { status: 204 }) };
    });

    renderPage();
    await readyEditor();
    const select = screen.getByTestId("scope-select").querySelector("select") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "novel-1" } });
    await waitFor(() => expect((screen.getByTestId("draft-textarea") as HTMLTextAreaElement).value).toBe(OVERRIDE));
    expect(queryClient.getQueryData<Record<string, unknown>>(["prompts", "detail", "writing.continuation", "novel-1"])?.effective_content).toBe(OVERRIDE);

    fireEvent.change(select, { target: { value: "" } });
    await waitFor(() => expect((screen.getByTestId("scope-chip-global") as HTMLButtonElement).getAttribute("aria-pressed")).toBe("true"));
    fireEvent.click(screen.getByTestId("reset-button"));
    fireEvent.click(screen.getByTestId("reset-go"));
    await waitFor(() => expect((screen.getByTestId("draft-textarea") as HTMLTextAreaElement).value).toBe(INHERITED));

    // The inactive novel entry inherited the deleted global source. A global
    // reset must unset it now, not wait for a catalog-wide cache expiry.
    expect(queryClient.getQueryData(["prompts", "detail", "writing.continuation", "novel-1"])).toBeUndefined();
    expect(novelDetailReads).toBe(1);

    fireEvent.change(select, { target: { value: "novel-1" } });
    await waitFor(() => expect((screen.getByTestId("draft-textarea") as HTMLTextAreaElement).value).toBe(INHERITED));
    expect(novelDetailReads).toBe(2);

    api.PUT.mockResolvedValue({ data: details["writing.continuation"], response: ok() });
    fireEvent.click(screen.getByTestId("save-button"));
    await waitFor(() => expect(api.PUT).toHaveBeenCalledWith("/api/prompts/{key}", expect.objectContaining({
      body: { content: INHERITED, novel_id: "novel-1" },
    })));
  });

  it("a novel reset leaves a sibling novel detail cached", async () => {
    const sibling = detail({
      override: { scope: "novel", content: "# Geschwister-Roman\n{{tail}}" },
      effective_content: "# Geschwister-Roman\n{{tail}}",
    });
    queryClient.setQueryData(["prompts", "detail", "writing.continuation", "novel-2"], sibling);
    api.DELETE.mockResolvedValue({ data: undefined, response: new Response(null, { status: 204 }) });

    renderPage();
    await readyEditor();
    const select = screen.getByTestId("scope-select").querySelector("select") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "novel-1" } });
    await screen.findByTestId("prompts-editor");
    fireEvent.click(screen.getByTestId("reset-button"));
    fireEvent.click(screen.getByTestId("reset-go"));
    await waitFor(() => expect((screen.getByTestId("reset-button") as HTMLButtonElement).disabled).toBe(false));

    expect(queryClient.getQueryData(["prompts", "detail", "writing.continuation", "novel-2"])).toBe(sibling);
  });

  it("MutationCache GC cannot roll the reset revision back into an unsaved draft", async () => {
    const OVERRIDE = "# Globaler Override\n{{tail}}";
    const INHERITED = "# Global-Standard\n{{tail}}";
    const UNSAVED = `${INHERITED} und ein ungesicherter Entwurf.`;
    details["writing.continuation"] = detail({
      override: { scope: "global", content: OVERRIDE },
      effective_content: OVERRIDE,
    });
    summaries = [summary({ override_global: true }), ...baseSummaries().slice(1)];
    api.DELETE.mockImplementation(async () => {
      details["writing.continuation"] = detail({ override: null, effective_content: INHERITED });
      summaries = baseSummaries();
      return { data: undefined, response: new Response(null, { status: 204 }) };
    });

    const router = renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("reset-button"));
    fireEvent.click(within(editor).getByTestId("reset-go"));
    await waitFor(() => expect((screen.getByTestId("draft-textarea") as HTMLTextAreaElement).value).toBe(INHERITED));

    await act(async () => { router.history.push("/elsewhere"); });
    await act(async () => { router.history.push("/settings/prompts"); });
    const remountedEditor = await screen.findByTestId("prompts-editor");
    const textarea = within(remountedEditor).getByTestId("draft-textarea") as HTMLTextAreaElement;
    expect(textarea.value).toBe(INHERITED);
    fireEvent.change(textarea, { target: { value: UNSAVED } });
    expect(textarea.value).toBe(UNSAVED);

    // The MutationCache entry may be collected once its page is gone. The
    // reset revision must live elsewhere, or this clear rolls the editor key
    // backward and discards the unsaved draft.
    await act(async () => {
      queryClient.getMutationCache().clear();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect((screen.getByTestId("draft-textarea") as HTMLTextAreaElement).value).toBe(UNSAVED);
    expect(screen.getByTestId("prompts-editor")).toBe(remountedEditor);
  });

  it("a failed fresh detail read keeps the stale detail out and still refreshes catalog marks", async () => {
    const OVERRIDE = "# Roman-Override\n{{tail}}";
    details["writing.continuation"] = detail({
      override: { scope: "novel", content: OVERRIDE },
      effective_content: OVERRIDE,
    });
    const originalGet = api.GET.getMockImplementation()! as GetMock;
    let detailReads = 0;
    let novelListReads = 0;
    api.GET.mockImplementation(async (path: string, init?: { params?: { path?: Record<string, string>; query?: Record<string, unknown> } }) => {
      if (path === "/api/prompts/{key}" && init?.params?.query?.novel_id === "novel-1") {
        detailReads += 1;
        if (detailReads > 1) {
          return { data: null, error: { detail: "detail unavailable" }, response: new Response(null, { status: 503 }) };
        }
      }
      if (path === "/api/prompts" && init?.params?.query?.novel_id === "novel-1") novelListReads += 1;
      return originalGet(path, init);
    });
    api.DELETE.mockImplementation(async () => {
      // The DELETE committed. Only the follow-up detail read is down.
      novelOverridePresent = false;
      details["writing.continuation"] = detail({ override: null, effective_content: BUNDLED });
      return { data: undefined, response: new Response(null, { status: 204 }) };
    });

    renderPage();
    await readyEditor();
    const select = screen.getByTestId("scope-select").querySelector("select") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "novel-1" } });
    const editor = await screen.findByTestId("prompts-editor");
    fireEvent.click(within(editor).getByTestId("reset-button"));
    fireEvent.click(within(editor).getByTestId("reset-go"));

    expect(await screen.findByTestId("prompts-outage")).toBeTruthy();
    await waitFor(() => expect(novelListReads).toBeGreaterThanOrEqual(2));
    expect(queryClient.getQueryData(["prompts", "detail", "writing.continuation", "novel-1"])).toBeUndefined();
    const marks = queryClient.getQueryData<Record<string, unknown>[]>(["prompts", "list", "novel-1"]);
    expect(marks?.find((row) => row.key === "writing.continuation")?.override_novel).toBe(false);
  });
});

describe("the diff", () => {
  it("opens the saved tiers side by side, the none face without an override", async () => {
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("diff-button"));
    const panel = await screen.findByTestId("diff-panel");
    const bundled = await within(panel).findByTestId("diff-bundled");
    expect(bundled.textContent).toContain(BUNDLED);
    expect(await within(panel).findByText(de["prompts.editor.diff.none"])).toBeTruthy();
  });

  it("with an override in force the override pane stands beside the bundled", async () => {
    details = {
      "writing.continuation": detail({ override: { scope: "global", content: "# Override-Stand" } }),
      "chat.ask": detail(),
      "knowledge.extract-entities": detail(),
      "knowledge.check-consistency": detail(),
    };
    scriptReads();
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("diff-button"));
    const panel = await screen.findByTestId("diff-panel");
    expect(await within(panel).findByTestId("diff-override").then((node) => node.textContent)).toContain("# Override-Stand");
  });
});

describe("the live test", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  /** A 200 SSE answer carrying the given frames. */
  function sse(frames: readonly string[]): Response {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const frame of frames) controller.enqueue(encoder.encode(frame));
        controller.close();
      },
    });
    return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
  }

  const contextFrame = (provider = "fake"): string =>
    `data: ${JSON.stringify({ context: { key: "writing.continuation", source: "draft", provider, novel_id: null, facts: { novel: "Dead Signal", chapter: "Nevada Echoes" } } })}\n\n`;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("the warning precedes the call: it stands while idle, the wire starts on the click", async () => {
    fetchMock.mockResolvedValue(sse([contextFrame(), "data: {\"delta\": \"Antwort\"}\n\n", "event: done\ndata: {}\n\n"]));
    renderPage();
    const editor = await readyEditor();
    const warning = within(editor).getByTestId("live-warning");
    expect(warning.textContent).toBe(de["prompts.live.warning"]);
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(within(editor).getByTestId("live-button"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/prompts/writing.continuation/live-test");
    expect(init.method).toBe("POST");
    // The pristine editor tests the saved effective: no content rides.
    expect(init.body).toBe(JSON.stringify({ content: null, novel_id: null }));
    expect(await within(editor).findByTestId("live-answer")).toBeTruthy();
    expect(within(editor).getByTestId("live-done").textContent).toContain(de["prompts.live.done"]);
  });

  it("the fake provider wears its honest mark; a named driver its kind", async () => {
    fetchMock.mockResolvedValue(sse([contextFrame(), "data: {\"delta\": \"A\"}\n\n", "event: done\ndata: {}\n\n"]));
    renderPage();
    let editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("live-button"));
    const context = await within(editor).findByTestId("live-context");
    expect(context.textContent).toContain(de["prompts.live.provider.fake"]);
    expect(context.textContent).toContain(de["prompts.live.provider.fakeNote"]);
    expect(context.textContent).not.toContain("Kein Provider konfiguriert");
    expect(context.textContent).toContain("Roman: Dead Signal");
    expect(context.textContent).toContain("Kapitel: Nevada Echoes");

    cleanup();
    queryClient.clear();
    fetchMock.mockResolvedValue(sse([contextFrame("openai-chat"), "event: done\ndata: {}\n\n"]));
    scriptReads();
    renderPage();
    editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("live-button"));
    const named = await within(editor).findByTestId("live-context");
    expect(named.textContent).toContain(de["prompts.live.provider.kind"].replace("{kind}", "openai-chat"));
    expect(named.textContent).not.toContain(de["prompts.live.provider.fakeNote"]);
  });

  it("the knowledge facts wear the catalog's labels, never the raw key", async () => {
    fetchMock.mockResolvedValue(sse([
      `data: ${JSON.stringify({
        context: {
          key: "knowledge.check-consistency",
          source: "effective",
          provider: "fake",
          novel_id: null,
          facts: { chars: "120", chapters: "2", entities: "3" },
        },
      })}\n\n`,
      "event: done\ndata: {}\n\n",
    ]));
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("live-button"));
    const context = await within(editor).findByTestId("live-context");
    expect(context.textContent).toContain(`${de["prompts.live.facts.chars"]}: 120`);
    expect(context.textContent).toContain(`${de["prompts.live.facts.chapters"]}: 2`);
    expect(context.textContent).toContain(`${de["prompts.live.facts.entities"]}: 3`);
    // The raw backend keys never reach the face when a label exists.
    expect(context.textContent).not.toContain("chapters: 2");
  });

  it("the deltas arrive live and land in the answer region", async () => {
    const encoder = new TextEncoder();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    fetchMock.mockResolvedValue(new Response(new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(contextFrame()));
        controller.enqueue(encoder.encode("data: {\"delta\": \"Erste Zeile.\"}\n\n"));
        void gate.then(() => {
          controller.enqueue(encoder.encode("data: {\"delta\": \" Zweite Zeile.\"}\n\n"));
          controller.enqueue(encoder.encode("event: done\ndata: {}\n\n"));
          controller.close();
        });
      },
    }), { status: 200, headers: { "Content-Type": "text/event-stream" } }));
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("live-button"));
    const answer = await within(editor).findByTestId("live-answer");
    await waitFor(() => expect(answer.textContent).toContain("Erste Zeile."));
    expect(answer.textContent).not.toContain("Zweite Zeile");
    release();
    await waitFor(() => expect(answer.textContent).toContain("Erste Zeile. Zweite Zeile."));
    expect(within(editor).getByTestId("live-done")).toBeTruthy();
  });

  it.each([
    [
      "rate-limited",
      429,
      (body: string) => new Response(body, { status: 429, headers: { "Retry-After": "14" } }),
      JSON.stringify({ detail: { code: "rate-limited", detail: "backend says" } }),
      de["prompts.live.error.rateLimited"],
      de["prompts.live.cooldown"].replace("{count}", "14"),
    ],
    [
      "key-unavailable",
      503,
      (body: string) => new Response(body, { status: 503 }),
      JSON.stringify({ detail: { code: "key-unavailable", detail: "backend says" } }),
      de["prompts.live.error.keyUnavailable"],
      null,
    ],
    [
      "no-context",
      409,
      (body: string) => new Response(body, { status: 409 }),
      JSON.stringify({ detail: { code: "no-context", detail: "backend says" } }),
      de["prompts.live.error.noContext"],
      null,
    ],
    [
      "provider",
      502,
      (body: string) => new Response(body, { status: 502 }),
      JSON.stringify({ detail: { code: "model-not-found", detail: "backend says" } }),
      de["prompts.live.error.provider"],
      null,
    ],
  ])("the %s pre-stream face localizes by code", async (_name, _status, respond, payload, copy, extra) => {
    fetchMock.mockResolvedValue(respond(payload));
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("live-button"));
    const face = await within(editor).findByTestId("live-error");
    expect(face.textContent).toContain(copy);
    if (extra !== null) expect(face.textContent).toContain(extra);
    expect(face.textContent).not.toContain("backend says");
  });

  it("a mid-stream error frame ends the face, not the page", async () => {
    fetchMock.mockResolvedValue(sse([contextFrame(), "event: error\ndata: {\"code\": \"provider-error\"}\n\n"]));
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("live-button"));
    const face = await within(editor).findByTestId("live-error");
    expect(face.textContent).toContain(de["prompts.live.error.generic"].replace("{code}", "provider-error"));
  });

  it("a stream that closes without a terminal frame is the interrupted face", async () => {
    fetchMock.mockResolvedValue(sse([contextFrame(), "data: {\"delta\": \"halb\"}\n\n"]));
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("live-button"));
    const face = await within(editor).findByTestId("live-error");
    expect(face.textContent).toContain(de["prompts.live.error.interrupted"]);
  });

  it("a draft the gate refuses shows the refusal family in the live card", async () => {
    // The 422 body is the gate's refusal wrapped in FastAPI's `detail` —
    // the same shape the save's answer carries.
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ detail: { reason: "budget", detail: "the assembled context exceeds the budget" } }), { status: 422 }));
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("live-button"));
    const face = await within(editor).findByTestId("refusal-face");
    expect(face.textContent).toContain(de["prompts.live.error.draftRefused"]);
    expect(face.textContent).toContain(de["prompts.refusal.headline"].replace("{reason}", de["prompts.refusal.reason.budget"]));
  });

  it("the cancel retires the running face back to the trigger", async () => {
    fetchMock.mockImplementation(() => new Promise(() => {}));
    renderPage();
    const editor = await readyEditor();
    fireEvent.click(within(editor).getByTestId("live-button"));
    expect(within(editor).getByTestId("live-cancel")).toBeTruthy();
    fireEvent.click(within(editor).getByTestId("live-cancel"));
    await waitFor(() => expect(within(editor).getByTestId("live-button")).toBeTruthy());
  });
});

describe("the honest gates and the shared chrome", () => {
  it("the outage face names the failure and the retry re-asks", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels") return { data: novelList, response: ok() };
      return { data: null, error: { detail: "down" }, response: new Response(null, { status: 503 }) };
    });
    renderPage();
    const outage = await screen.findByTestId("prompts-outage");
    expect(outage.textContent).toContain(de["prompts.loadFailed"]);
    api.GET.mockImplementation(async (path: string, init?: { params?: { path?: Record<string, string>; query?: Record<string, unknown> } }) => {
      if (path === "/api/writing/novels") return { data: novelList, response: ok() };
      if (path === "/api/prompts") return { data: summaries, response: ok() };
      const key = init?.params?.path?.key ?? "";
      return { data: details[key] ?? detail(), response: ok() };
    });
    fireEvent.click(screen.getByTestId("prompts-retry"));
    expect(await screen.findByTestId("prompts-editor")).toBeTruthy();
  });

  it("a failed detail read is the outage face, never a perpetual loading card; the retry re-asks it", async () => {
    // The list and the novels answer; only the editor's detail read fails.
    api.GET.mockImplementation(async (path: string, init?: { params?: { path?: Record<string, string> } }) => {
      if (path === "/api/writing/novels") return { data: novelList, response: ok() };
      if (path === "/api/prompts") return { data: summaries, response: ok() };
      return { data: null, error: { detail: "detail down" }, response: new Response(null, { status: 503 }) };
    });
    renderPage();
    const outage = await screen.findByTestId("prompts-outage");
    expect(outage.textContent).toContain(de["prompts.loadFailed"]);
    // No loading card stands in the editor's place — the page is one outage.
    expect(screen.queryByTestId("prompts-editor")).toBeNull();
    // The retry re-asks the detail: the editor stands.
    api.GET.mockImplementation(async (path: string, init?: { params?: { path?: Record<string, string>; query?: Record<string, unknown> } }) => {
      if (path === "/api/writing/novels") return { data: novelList, response: ok() };
      if (path === "/api/prompts") return { data: summaries, response: ok() };
      const key = init?.params?.path?.key ?? "";
      return { data: details[key] ?? detail(), response: ok() };
    });
    fireEvent.click(screen.getByTestId("prompts-retry"));
    expect(await screen.findByTestId("prompts-editor")).toBeTruthy();
  });

  it("the loading face stands while the reads ask", async () => {
    api.GET.mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(await screen.findByText(de["prompts.loading"])).toBeTruthy();
  });

  it("the hub chrome carries the three routes, the active face on Prompts", async () => {
    renderPage();
    await readyEditor();
    const nav = screen.getByRole("navigation", { name: de["shell.hub.label"] });
    const links = Array.from(nav.querySelectorAll("a"));
    expect(links.map((link) => link.textContent)).toEqual([
      de["shell.hub.general"],
      de["shell.hub.aiRules"],
      de["shell.hub.prompts"],
    ]);
    expect(links[2]?.getAttribute("aria-current")).toBe("page");
  });

  it("the Ablehnungsgründe expander carries the drafted families", async () => {
    renderPage();
    const editor = await readyEditor();
    const expander = within(editor).getByTestId("refusal-reasons");
    expect(expander.textContent).toContain(de["prompts.reasons.syntax.title"]);
    expect(expander.textContent).toContain(de["prompts.reasons.variable.title"]);
    expect(expander.textContent).toContain(de["prompts.reasons.cycle.title"]);
    expect(expander.textContent).toContain(de["prompts.reasons.marker.title"]);
  });
});
