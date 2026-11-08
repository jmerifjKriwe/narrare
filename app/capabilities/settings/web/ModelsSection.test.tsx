// @vitest-environment jsdom
/**
 * The models section and the task rows it feeds: a model names a provider and
 * a model string, and everything the rows say composes from those two — the
 * list rows, the assignment options, the effective lines. The provider select
 * is the form's new door (the model carries no endpoint and no key of its
 * own), the mount's reads survive one section's failure beside the alert, and
 * a request that never reaches the service is named where it happened.
 *
 * The API client is mocked at its module boundary: the cases here are about
 * what the sections say, and the requests are verified by the backend and
 * E2E suites against the real stack.
 */
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { t } from "@shell/lib/i18n";

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

import { ModelsSection } from "./ModelsSection";
import { TasksSection, labelOf } from "./TasksSection";
import type { Provider } from "./ProvidersSection";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

const PROVIDER = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "ZAI",
  kind: "fake",
  base_url: null,
  models_url: null,
  vendor: null,
  api_key_mask: null,
};

const VENDORED_PROVIDER = {
  ...PROVIDER,
  id: "44444444-4444-4444-4444-444444444444",
  name: "Z.ai direct",
  kind: "openai-chat",
  base_url: "https://api.z.ai/api/paas/v4",
  vendor: "zai",
};

/** The presets payload's shape, as the endpoint returns it (two of the nine). */
const PRESETS = [
  {
    id: "zai",
    label: "Z.ai",
    kind: "openai-chat",
    base_url: "https://api.z.ai/api/paas/v4",
    models_url: null,
    vendor: "zai",
    model: "glm-5.3",
    note_key: null,
    models: ["glm-5.3", "glm-5.3-flash", "glm-5.3-turbo"],
    snapshot_date: "2026-10-27",
  },
  {
    id: "zai-coding-plan",
    label: "Z.ai Coding Plan",
    kind: "openai-chat",
    base_url: "https://api.z.ai/api/coding/paas/v4",
    models_url: null,
    vendor: "zai-coding-plan",
    model: "glm-5.3",
    note_key: "settings.providers.note.zaiCodingPlan",
    models: ["glm-5.3"],
    snapshot_date: null,
  },
];

const DEFAULT_MODEL = {
  id: "22222222-2222-2222-2222-222222222222",
  name: "Default",
  provider_id: PROVIDER.id,
  provider_name: "ZAI",
  model: "glm-5.3-flash",
  is_default: true,
  context_window: null,
  max_output_tokens: null,
  temperature: null,
  request_timeout: null,
  created_at: "2026-11-08T10:00:00Z",
  updated_at: "2026-11-08T10:00:00Z",
};

const SECOND_MODEL = {
  ...DEFAULT_MODEL,
  id: "33333333-3333-3333-3333-333333333333",
  name: "Second",
  is_default: false,
};

const TASKS = [
  {
    task_key: "writing.continuation",
    profile_id: DEFAULT_MODEL.id,
    profile_name: "Default",
    kind: "fake",
    assignable: true,
  },
  {
    task_key: "chat.ask",
    profile_id: null,
    profile_name: null,
    kind: "openai-chat",
    assignable: true,
  },
  {
    task_key: "settings.test",
    profile_id: null,
    profile_name: null,
    kind: "audit",
    assignable: false,
  },
];

const NO_GUARD = { dirty: false, ask: async () => true };

function renderSections(
  providers: Provider[] = [PROVIDER],
  presets: typeof PRESETS | null = PRESETS,
  modelSeed: { model: string; token: number } | null = null,
): ReturnType<typeof render> {
  return render(
    <>
      <ModelsSection
        providers={providers}
        presets={presets}
        models={[DEFAULT_MODEL, SECOND_MODEL]}
        reload={async () => {}}
        guard={NO_GUARD}
        onDirty={() => {}}
        modelSeed={modelSeed}
      />
      <TasksSection
        models={[DEFAULT_MODEL, SECOND_MODEL]}
        assignments={[]}
        tasks={TASKS}
        reload={async () => {}}
      />
    </>,
  );
}

/** Rerender with new seed state, as the panel would between emissions. */
function rerenderSections(
  ui: ReturnType<typeof render>,
  providers: Provider[],
  presets: typeof PRESETS | null,
  modelSeed: { model: string; token: number } | null,
): void {
  ui.rerender(
    <>
      <ModelsSection
        providers={providers}
        presets={presets}
        models={[DEFAULT_MODEL, SECOND_MODEL]}
        reload={async () => {}}
        guard={NO_GUARD}
        onDirty={() => {}}
        modelSeed={modelSeed}
      />
      <TasksSection
        models={[DEFAULT_MODEL, SECOND_MODEL]}
        assignments={[]}
        tasks={TASKS}
        reload={async () => {}}
      />
    </>,
  );
}

function ok(): Response {
  return new Response(null, { status: 200 });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("the task rows", () => {
  it("name the model that serves each task, composed as provider · model", async () => {
    renderSections();

    const label = labelOf(DEFAULT_MODEL);
    expect(label).toBe("ZAI · glm-5.3-flash");
    const via = t("settings.assignments.via", { model: label });
    expect(screen.getAllByText(via, { exact: false })).toHaveLength(1);
  });

  it("show the environment kind when no model serves", async () => {
    renderSections();

    const environment = t("settings.assignments.environment", {
      kind: t("settings.providers.kind.openai-chat"),
    });
    expect(screen.getByText(environment)).toBeTruthy();
  });

  it("offer the models composed, so a task points at provider and model together", async () => {
    renderSections();

    const select = screen.getByLabelText(t("settings.task.writing.continuation"));
    const options = Array.from(select.querySelectorAll("option")).map((option) => option.textContent);
    expect(options).toContain(labelOf(DEFAULT_MODEL));
    expect(options).toContain(labelOf(SECOND_MODEL));
  });

  it("label the audit-only key and offer it no assignment control", async () => {
    renderSections();

    // The server marks `settings.test` audit-only: the probe tests the model
    // the user picks, so the row must not claim an effective provider, must
    // not offer an assignment, and must not print the internal key.
    const label = t("settings.tasks.settings.test");
    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByText(t("settings.profiles.taskAuditOnly"))).toBeTruthy();
    expect(screen.queryByLabelText(label)).toBeNull();
    expect(screen.queryByText(/settings\.test/)).toBeNull();
  });
});

describe("the model form's inputs", () => {
  it("keep spellcheck and autofill off the technical values", async () => {
    renderSections();

    for (const label of [t("settings.profiles.nameLabel"), t("settings.profiles.modelLabel")]) {
      const input = screen.getByLabelText(label);
      expect(input.getAttribute("spellcheck")).toBe("false");
      expect(input.getAttribute("autocomplete")).toBe("off");
    }
  });

  it("offer no endpoint and no key: the provider carries both", async () => {
    renderSections();

    expect(screen.queryByLabelText(t("settings.providers.baseUrlLabel"))).toBeNull();
    expect(screen.queryByLabelText(t("settings.providers.apiKeyLabel"))).toBeNull();
    expect(screen.getByLabelText(t("settings.profiles.providerLabel"))).toBeTruthy();
  });

  it("send provider_id and model on a create", async () => {
    api.POST.mockResolvedValue({ data: DEFAULT_MODEL, response: new Response(null, { status: 201 }) });
    renderSections();

    await userEvent.type(screen.getByLabelText(t("settings.profiles.nameLabel")), "Neu");
    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.profiles.providerLabel")),
      PROVIDER.id,
    );
    await userEvent.type(screen.getByLabelText(t("settings.profiles.modelLabel")), "glm-5.3-flash");
    await userEvent.click(screen.getByRole("button", { name: t("settings.profiles.create") }));

    expect(api.POST).toHaveBeenCalledWith(
      "/api/settings/models",
      expect.objectContaining({
        body: expect.objectContaining({ provider_id: PROVIDER.id, model: "glm-5.3-flash" }),
      }),
    );
  });

  it("name the missing provider instead of silently disabling the save", async () => {
    renderSections();

    // The blank create opens on an explicit, disabled placeholder option —
    // a select that merely showed nothing left the disabled save unexplained.
    const select = screen.getByLabelText(
      t("settings.profiles.providerLabel"),
    ) as HTMLSelectElement;
    expect(select.value).toBe("");
    const placeholder = select.querySelector('option[value=""]') as HTMLOptionElement;
    expect(placeholder).toBeTruthy();
    expect(placeholder.textContent).toBe(t("settings.profiles.chooseProvider"));
    expect(placeholder.disabled).toBe(true);

    await userEvent.type(screen.getByLabelText(t("settings.profiles.nameLabel")), "Neu");
    await userEvent.type(screen.getByLabelText(t("settings.profiles.modelLabel")), "glm-5.3-flash");
    const save = screen.getByRole("button", {
      name: t("settings.profiles.create"),
    }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);

    await userEvent.selectOptions(select, PROVIDER.id);
    expect(save.disabled).toBe(false);
  });
});

describe("the model input's datalist", () => {
  it("suggests the chosen provider's vendor models, with the catalog's date", async () => {
    renderSections([VENDORED_PROVIDER]);

    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.profiles.providerLabel")),
      VENDORED_PROVIDER.id,
    );
    const input = screen.getByLabelText(t("settings.profiles.modelLabel")) as HTMLInputElement;
    expect(input.getAttribute("list")).toBeTruthy();
    const datalist = document.getElementById(input.getAttribute("list") as string);
    expect(datalist?.tagName.toLowerCase()).toBe("datalist");
    const suggested = Array.from(datalist?.querySelectorAll("option") ?? []).map(
      (option) => option.value,
    );
    expect(suggested).toEqual(["glm-5.3", "glm-5.3-flash", "glm-5.3-turbo"]);
    expect(screen.getByText(t("settings.profiles.catalogDated", { date: "2026-10-27" }))).toBeTruthy();
  });

  it("stays empty and quiet when the provider names no vendor, free text still saving", async () => {
    api.POST.mockResolvedValue({ data: DEFAULT_MODEL, response: new Response(null, { status: 201 }) });
    renderSections();

    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.profiles.providerLabel")),
      PROVIDER.id,
    );
    const input = screen.getByLabelText(t("settings.profiles.modelLabel")) as HTMLInputElement;
    const datalist = document.getElementById(input.getAttribute("list") as string);
    expect(datalist?.querySelectorAll("option")).toHaveLength(0);
    expect(screen.queryByText(t("settings.profiles.catalogDated", { date: "2026-10-27" }))).toBeNull();
    expect(screen.queryByText(t("settings.profiles.catalogDateUnknown"))).toBeNull();

    // The picker being empty is not a gate: a model the catalog does not
    // carry still saves, spelled by hand.
    await userEvent.type(input, "my-own-finetune");
    await userEvent.type(screen.getByLabelText(t("settings.profiles.nameLabel")), "Neu");
    await userEvent.click(screen.getByRole("button", { name: t("settings.profiles.create") }));

    expect(api.POST).toHaveBeenCalledWith(
      "/api/settings/models",
      expect.objectContaining({
        body: expect.objectContaining({ model: "my-own-finetune" }),
      }),
    );
  });

  it("says the date is unknown when the snapshot names none", async () => {
    const [dated, dateless] = PRESETS;
    renderSections([VENDORED_PROVIDER, { ...VENDORED_PROVIDER, id: "55555555-5555-5555-5555-555555555555", vendor: "zai-coding-plan" }], [dated, dateless]);

    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.profiles.providerLabel")),
      "55555555-5555-5555-5555-555555555555",
    );

    expect(screen.getByText(t("settings.profiles.catalogDateUnknown"))).toBeTruthy();
    expect(screen.queryByText(t("settings.profiles.catalogDated", { date: "2026-10-27" }))).toBeNull();
  });
});

describe("the preset-created provider's model seed", () => {
  it("pre-seeds the model input once, editable and clearable", async () => {
    const ui = renderSections();

    // Nothing yet: no provider has been created from a preset.
    expect((screen.getByLabelText(t("settings.profiles.modelLabel")) as HTMLInputElement).value).toBe(
      "",
    );

    // The panel emits the seed; the input shows it as an editable starting value.
    rerenderSections(ui, [PROVIDER], PRESETS, { model: "glm-5.3", token: 1 });
    const input = screen.getByLabelText(t("settings.profiles.modelLabel")) as HTMLInputElement;
    expect(input.value).toBe("glm-5.3");

    // The user's own edit wins: a later emission for another provider does
    // not overwrite what is in the input.
    await userEvent.type(input, "-flash");
    rerenderSections(ui, [PROVIDER], PRESETS, { model: "glm-5.3-turbo", token: 2 });
    expect((screen.getByLabelText(t("settings.profiles.modelLabel")) as HTMLInputElement).value).toBe(
      "glm-5.3-flash",
    );

    // Clearing is the user's act, and it sticks: rerenders that carry the
    // panel's last seed again (any reload does) re-apply nothing.
    const cleared = screen.getByLabelText(t("settings.profiles.modelLabel")) as HTMLInputElement;
    await userEvent.clear(cleared);
    rerenderSections(ui, [PROVIDER], PRESETS, { model: "glm-5.3-turbo", token: 2 });
    expect((screen.getByLabelText(t("settings.profiles.modelLabel")) as HTMLInputElement).value).toBe(
      "",
    );
    expect(
      (screen.getByRole("button", { name: t("settings.profiles.create") }) as HTMLButtonElement)
        .disabled,
    ).toBe(true); // cleared normally: the model is required again
  });

  it("never lands over a typed model or in an opened edit", async () => {
    const ui = renderSections();

    // The user typed a model first; the seed for a just-created provider
    // arrives and must not replace what they wrote.
    await userEvent.type(
      screen.getByLabelText(t("settings.profiles.modelLabel")),
      "my-own-finetune",
    );
    rerenderSections(ui, [PROVIDER], PRESETS, { model: "glm-5.3", token: 1 });
    expect((screen.getByLabelText(t("settings.profiles.modelLabel")) as HTMLInputElement).value).toBe(
      "my-own-finetune",
    );

    // An opened edit always carries the stored model: a seed arriving then
    // edits nothing the user did not open themselves.
    rerenderSections(ui, [PROVIDER], PRESETS, null);
    await userEvent.click(screen.getAllByRole("button", { name: t("settings.profiles.edit") })[0]);
    expect((screen.getByLabelText(t("settings.profiles.modelLabel")) as HTMLInputElement).value).toBe(
      DEFAULT_MODEL.model,
    );
    rerenderSections(ui, [PROVIDER], PRESETS, { model: "glm-5.3-turbo", token: 2 });
    expect((screen.getByLabelText(t("settings.profiles.modelLabel")) as HTMLInputElement).value).toBe(
      DEFAULT_MODEL.model,
    );
  });
});

describe("the mount's reads through the panel", () => {
  it("are the page's own five, asked together on mount", async () => {
    const { ProvidersPanel } = await import("./ProvidersPanel");
    api.GET.mockImplementation(async (path: string) => {
      switch (path) {
        case "/api/settings/providers":
          return { data: [PROVIDER], response: ok() };
        case "/api/settings/models":
          return { data: [DEFAULT_MODEL], response: ok() };
        case "/api/settings/assignments":
          return { data: [], response: ok() };
        case "/api/settings/tasks":
          return { data: TASKS, response: ok() };
        case "/api/settings/presets":
          return { data: PRESETS, response: ok() };
        default:
          throw new Error(`unexpected GET ${path}`);
      }
    });

    render(<ProvidersPanel />);
    // The rows only exist after the mount's fetch lands: the composed label
    // shows in the model row and in every task select's options.
    expect((await screen.findAllByText("ZAI · glm-5.3-flash")).length).toBeGreaterThan(0);
    const paths = api.GET.mock.calls.map((call) => call[0]);
    expect(paths).toEqual(
      expect.arrayContaining([
        "/api/settings/providers",
        "/api/settings/models",
        "/api/settings/assignments",
        "/api/settings/tasks",
        "/api/settings/presets",
      ]),
    );
  });

  it("keep the lists when the task list fails, with the alert beside them", async () => {
    const { ProvidersPanel } = await import("./ProvidersPanel");
    api.GET.mockImplementation(async (path: string) => {
      switch (path) {
        case "/api/settings/providers":
          return { data: [PROVIDER], response: ok() };
        case "/api/settings/models":
          return { data: [DEFAULT_MODEL], response: ok() };
        case "/api/settings/assignments":
          return { data: [], response: ok() };
        case "/api/settings/tasks":
          throw new TypeError("Failed to fetch");
        case "/api/settings/presets":
          return { data: PRESETS, response: ok() };
        default:
          throw new Error(`unexpected GET ${path}`);
      }
    });

    render(<ProvidersPanel />);
    expect(await screen.findAllByText(labelOf(DEFAULT_MODEL)).then((rows) => rows.length)).toBeGreaterThan(0);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("settings.profiles.errorLoad"));
    // The failure sits above everything it concerns: the alert precedes each
    // section's heading in the page's own order.
    for (const key of ["settings.providers", "settings.models", "settings.assignments"] as const) {
      const heading = screen.getByRole("heading", { name: t(key) });
      expect(heading.compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING).toBeFalsy();
    }
  });

  it("announce the load while the lists are still on their way", async () => {
    const { ProvidersPanel } = await import("./ProvidersPanel");
    // Nothing ever answers: the mount stays between "asked" and "arrived",
    // exactly the span the loading status exists to speak in.
    api.GET.mockImplementation(() => new Promise(() => {}));

    render(<ProvidersPanel />);
    const status = await screen.findByRole("status");
    expect(status.textContent).toContain(t("settings.profiles.loading"));
  });

  it("keep the sections when the presets read fails, with the alert beside them", async () => {
    const { ProvidersPanel } = await import("./ProvidersPanel");
    api.GET.mockImplementation(async (path: string) => {
      switch (path) {
        case "/api/settings/providers":
          return { data: [PROVIDER], response: ok() };
        case "/api/settings/models":
          return { data: [DEFAULT_MODEL], response: ok() };
        case "/api/settings/assignments":
          return { data: [], response: ok() };
        case "/api/settings/tasks":
          return { data: TASKS, response: ok() };
        case "/api/settings/presets":
          throw new TypeError("Failed to fetch");
        default:
          throw new Error(`unexpected GET ${path}`);
      }
    });

    render(<ProvidersPanel />);
    // The sections the four other reads feed still render: rows, forms and
    // the provider select are all there — only the preset select and the
    // datalist vocabulary are absent (their props arrived as null).
    expect(await screen.findAllByText(labelOf(DEFAULT_MODEL)).then((rows) => rows.length)).toBeGreaterThan(0);
    expect(screen.getByLabelText(t("settings.profiles.modelLabel"))).toBeTruthy();
    expect(screen.getByLabelText(t("settings.profiles.providerLabel"))).toBeTruthy();
    expect(screen.queryByLabelText(t("settings.providers.presetLabel"))).toBeNull();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("settings.profiles.errorLoad"));
  });

  it("seeds the model form with the preset's model after a provider is created from it", async () => {
    const { ProvidersPanel } = await import("./ProvidersPanel");
    api.GET.mockImplementation(async (path: string) => {
      switch (path) {
        case "/api/settings/providers":
          return { data: [PROVIDER], response: ok() };
        case "/api/settings/models":
          return { data: [DEFAULT_MODEL], response: ok() };
        case "/api/settings/assignments":
          return { data: [], response: ok() };
        case "/api/settings/tasks":
          return { data: TASKS, response: ok() };
        case "/api/settings/presets":
          return { data: PRESETS, response: ok() };
        default:
          throw new Error(`unexpected GET ${path}`);
      }
    });

    render(<ProvidersPanel />);
    expect(await screen.findAllByText("ZAI · glm-5.3-flash").then((rows) => rows.length)).toBeGreaterThan(0);

    // Create a provider from the Coding Plan preset.
    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.providers.presetLabel")),
      "zai-coding-plan",
    );
    api.POST.mockResolvedValue({
      data: { ...PROVIDER, id: "99999999-9999-9999-9999-999999999999" },
      response: new Response(null, { status: 201 }),
    });
    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.create") }));

    // The model form now starts at the preset's model, as an editable value.
    const input = await screen.findByLabelText(t("settings.profiles.modelLabel")) as HTMLInputElement;
    expect(input.value).toBe("glm-5.3");
  });
});

describe("a secondary action whose request cannot be sent", () => {
  it("names a delete that never reaches the service", async () => {
    renderSections();
    api.DELETE.mockRejectedValue(new TypeError("Failed to fetch"));

    await userEvent.click(screen.getAllByRole("button", { name: t("settings.profiles.delete") })[0]);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("settings.profiles.errorDelete"));
  });

  it("names a test connection that never reaches the service", async () => {
    renderSections();
    api.POST.mockRejectedValue(new TypeError("Failed to fetch"));

    await userEvent.click(screen.getAllByRole("button", { name: t("settings.profiles.test") })[0]);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("settings.profiles.errorAction"));
  });

  it("names an assignment that never reaches the service", async () => {
    renderSections();
    api.PUT.mockRejectedValue(new TypeError("Failed to fetch"));

    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.task.writing.continuation")),
      SECOND_MODEL.id,
    );

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("settings.profiles.errorAction"));
  });
});
