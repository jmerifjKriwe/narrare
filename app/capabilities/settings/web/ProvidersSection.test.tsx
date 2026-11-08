// @vitest-environment jsdom
/**
 * The providers section: the saved endpoints their models hang off. The key
 * is the one secret here, so the cases pin its round-trip — the create is
 * the one response that shows the full key, an update with an empty key
 * field keeps the stored one — plus the form's technical fields, the delete
 * guard's refusal, and the row's model discovery. The dirty form asks before
 * it is thrown away, through the guard the panel shares across sections.
 *
 * The API client is mocked at its module boundary: the cases here are about
 * what the section says, and the requests are verified by the backend and
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

import { ProvidersSection } from "./ProvidersSection";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

const PROVIDER = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Vendor",
  kind: "openai-chat",
  base_url: "http://127.0.0.1:9/v1",
  models_url: null,
  vendor: null,
  api_key_mask: "sk-…cret",
};

/** The presets payload's shape, as the endpoint returns it (three of the nine). */
const PRESETS = [
  {
    id: "opencode-go",
    label: "OpenCode Go",
    kind: "openai-chat",
    base_url: "https://opencode.ai/inference/go/openai/v1",
    models_url: "https://opencode.ai/inference/go/v1/models",
    vendor: "opencode-go",
    model: "glm-5.3-flash",
    note_key: null,
    models: ["glm-5.3-flash", "glm-5.3"],
    snapshot_date: "2026-10-27",
  },
  {
    id: "zai",
    label: "Z.ai",
    kind: "openai-chat",
    base_url: "https://api.z.ai/api/paas/v4",
    models_url: null,
    vendor: "zai",
    model: "glm-5.3",
    note_key: null,
    models: ["glm-5.3", "glm-5.3-flash"],
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

const NO_GUARD = { dirty: false, ask: async () => true };

function renderSection(presets: typeof PRESETS | null = PRESETS): void {
  render(
    <ProvidersSection
      providers={[PROVIDER]}
      presets={presets}
      reload={async () => {}}
      guard={NO_GUARD}
      onDirty={() => {}}
      onModelSeed={() => {}}
    />,
  );
}

function ok(): Response {
  return new Response(null, { status: 200 });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("the provider form's inputs", () => {
  it("keeps spellcheck and autofill off the technical values", async () => {
    renderSection();

    for (const label of [
      t("settings.providers.nameLabel"),
      t("settings.providers.baseUrlLabel"),
      t("settings.providers.modelsUrlLabel"),
      t("settings.providers.vendorLabel"),
    ]) {
      const input = screen.getByLabelText(label);
      expect(input.getAttribute("spellcheck")).toBe("false");
      expect(input.getAttribute("autocomplete")).toBe("off");
    }

    const key = screen.getByLabelText(t("settings.providers.apiKeyLabel"));
    expect(key.getAttribute("type")).toBe("password");
    expect(key.getAttribute("autocomplete")).toBe("new-password");
    expect(key.getAttribute("spellcheck")).toBe("false");
  });
});

describe("the kind select", () => {
  it("offers the server's three kinds, anthropic under its catalog label", () => {
    renderSection();

    const kind = screen.getByLabelText(t("settings.providers.kindLabel")) as HTMLSelectElement;
    const options = Array.from(kind.options).map((option) => option.textContent);
    expect(options).toEqual([
      t("settings.providers.kind.fake"),
      t("settings.providers.kind.openai-chat"),
      t("settings.providers.kind.anthropic"),
    ]);
  });
});

describe("the preset select", () => {
  it("opens the create on the custom choice — the blank form — and offers the presets", () => {
    renderSection();

    const preset = screen.getByLabelText(t("settings.providers.presetLabel")) as HTMLSelectElement;
    expect(preset.value).toBe("");
    const options = Array.from(preset.options).map((option) => option.textContent);
    expect(options).toEqual([
      t("settings.providers.presetCustom"),
      ...PRESETS.map((entry) => entry.label),
    ]);
  });

  it("is absent while the presets are still on their way", () => {
    renderSection(null);

    expect(screen.queryByLabelText(t("settings.providers.presetLabel"))).toBeNull();
  });

  it("is absent while editing: the provider is already what it is", async () => {
    renderSection();

    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.edit") }));

    expect(screen.queryByLabelText(t("settings.providers.presetLabel"))).toBeNull();
  });

  it("fills name, kind, base URL, models URL and vendor, and clears a typed key", async () => {
    renderSection();

    // A key typed for one endpoint must never survive the fill: the choice
    // is a *new* endpoint, and its key field starts clean — whatever was in
    // the field belonged to another vendor's terms.
    const key = screen.getByLabelText(t("settings.providers.apiKeyLabel")) as HTMLInputElement;
    await userEvent.type(key, "sk-for-someone-else");
    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.providers.presetLabel")),
      "zai-coding-plan",
    );

    expect(key.value).toBe("");
    expect((screen.getByLabelText(t("settings.providers.nameLabel")) as HTMLInputElement).value).toBe(
      "Z.ai Coding Plan",
    );
    expect((screen.getByLabelText(t("settings.providers.kindLabel")) as HTMLSelectElement).value).toBe(
      "openai-chat",
    );
    expect((screen.getByLabelText(t("settings.providers.baseUrlLabel")) as HTMLInputElement).value).toBe(
      "https://api.z.ai/api/coding/paas/v4",
    );
    expect(
      (screen.getByLabelText(t("settings.providers.modelsUrlLabel")) as HTMLInputElement).value,
    ).toBe("");
    expect((screen.getByLabelText(t("settings.providers.vendorLabel")) as HTMLInputElement).value).toBe(
      "zai-coding-plan",
    );

    // And nothing of the cleared key reaches the request either.
    api.POST.mockResolvedValue({
      data: { ...PROVIDER, id: "22222222-2222-2222-2222-222222222222", api_key: "sk-preset" },
      response: new Response(null, { status: 201 }),
    });
    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.create") }));
    const body = api.POST.mock.calls[0][1].body as Record<string, string>;
    expect(body.api_key).toBeUndefined();
    expect(JSON.stringify(body)).not.toContain("sk-for-someone-else");
  });

  it("fills the models URL when the preset keeps its list on its own path", async () => {
    renderSection();

    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.providers.presetLabel")),
      "opencode-go",
    );

    expect(
      (screen.getByLabelText(t("settings.providers.modelsUrlLabel")) as HTMLInputElement).value,
    ).toBe("https://opencode.ai/inference/go/v1/models");
    expect((screen.getByLabelText(t("settings.providers.baseUrlLabel")) as HTMLInputElement).value).toBe(
      "https://opencode.ai/inference/go/openai/v1",
    );
  });

  it("keeps the fill editable: a typed-over field still saves", async () => {
    api.POST.mockResolvedValue({
      data: { ...PROVIDER, id: "22222222-2222-2222-2222-222222222222", api_key: "sk-preset" },
      response: new Response(null, { status: 201 }),
    });
    renderSection();

    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.providers.presetLabel")),
      "zai-coding-plan",
    );
    const name = screen.getByLabelText(t("settings.providers.nameLabel")) as HTMLInputElement;
    await userEvent.clear(name);
    await userEvent.type(name, "Mein Z.ai");
    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.create") }));

    expect(api.POST).toHaveBeenCalledWith(
      "/api/settings/providers",
      expect.objectContaining({
        body: expect.objectContaining({
          name: "Mein Z.ai",
          kind: "openai-chat",
          base_url: "https://api.z.ai/api/coding/paas/v4",
          vendor: "zai-coding-plan",
        }),
      }),
    );
    const body = api.POST.mock.calls[0][1].body as Record<string, string>;
    expect(body.api_key).toBeUndefined(); // cleared, and never typed: nothing sent
  });

  it("speaks the preset's note while the one that owes it is chosen", async () => {
    renderSection();

    const preset = screen.getByLabelText(t("settings.providers.presetLabel")) as HTMLSelectElement;
    await userEvent.selectOptions(preset, "zai-coding-plan");
    expect(screen.getByText(t("settings.providers.note.zaiCodingPlan"))).toBeTruthy();

    await userEvent.selectOptions(preset, "zai");
    expect(screen.queryByText(t("settings.providers.note.zaiCodingPlan"))).toBeNull();
  });

  it("describes the note to the select, so focus hears it", async () => {
    renderSection();

    const preset = screen.getByLabelText(t("settings.providers.presetLabel")) as HTMLSelectElement;
    await userEvent.selectOptions(preset, "zai-coding-plan");
    const note = screen.getByText(t("settings.providers.note.zaiCodingPlan"));
    expect(preset.getAttribute("aria-describedby")).toBe(note.id);

    await userEvent.selectOptions(preset, "zai");
    expect(preset.getAttribute("aria-describedby")).toBeNull();
  });

  it("clears a failed save's notice when the blank form is chosen", async () => {
    api.POST.mockResolvedValue({ data: undefined, response: new Response(null, { status: 500 }) });
    renderSection();

    // The failed save is a preset attempt's: the preset is really chosen
    // first, so switching away is a real change of the select's value.
    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.providers.presetLabel")),
      "zai-coding-plan",
    );
    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.create") }));
    expect(await screen.findByText(t("settings.providers.errorSave"))).toBeTruthy();

    // Back to the blank form: the old attempt's failure is not this one's.
    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.providers.presetLabel")),
      "",
    );
    expect(screen.queryByText(t("settings.providers.errorSave"))).toBeNull();
    expect((screen.getByLabelText(t("settings.providers.nameLabel")) as HTMLInputElement).value).toBe(
      "",
    );
    expect((screen.getByLabelText(t("settings.providers.vendorLabel")) as HTMLInputElement).value).toBe(
      "",
    );
  });

  it("hands the chosen preset's model to the panel once, only on a stored create", async () => {
    const onModelSeed = vi.fn();
    api.POST.mockResolvedValue({
      data: { ...PROVIDER, id: "22222222-2222-2222-2222-222222222222" },
      response: new Response(null, { status: 201 }),
    });
    render(
      <ProvidersSection
        providers={[PROVIDER]}
        presets={PRESETS}
        reload={async () => {}}
        guard={NO_GUARD}
        onDirty={() => {}}
        onModelSeed={onModelSeed}
      />,
    );

    // A choice alone emits nothing: only the stored provider does.
    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.providers.presetLabel")),
      "opencode-go",
    );
    expect(onModelSeed).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.create") }));
    expect(onModelSeed).toHaveBeenCalledTimes(1);
    expect(onModelSeed).toHaveBeenCalledWith(
      "22222222-2222-2222-2222-222222222222",
      "glm-5.3-flash",
    );

    // A FAILED create from a preset emits nothing either: the preset is
    // chosen again after the reset form, so this attempt really is a
    // preset create — and its refusal stores nothing to seed from.
    onModelSeed.mockClear();
    api.POST.mockResolvedValue({ data: undefined, response: new Response(null, { status: 500 }) });
    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.providers.presetLabel")),
      "opencode-go",
    );
    expect(
      (screen.getByLabelText(t("settings.providers.nameLabel")) as HTMLInputElement).value,
    ).toBe("OpenCode Go"); // the attempt below really rides the preset
    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.create") }));
    expect(await screen.findByText(t("settings.providers.errorSave"))).toBeTruthy();
    expect(onModelSeed).not.toHaveBeenCalled();
  });

  it("returns to the blank form when the custom choice is picked again", async () => {
    renderSection();

    const preset = screen.getByLabelText(t("settings.providers.presetLabel")) as HTMLSelectElement;
    await userEvent.selectOptions(preset, "zai-coding-plan");
    await userEvent.selectOptions(preset, "");

    expect((screen.getByLabelText(t("settings.providers.nameLabel")) as HTMLInputElement).value).toBe(
      "",
    );
    expect((screen.getByLabelText(t("settings.providers.vendorLabel")) as HTMLInputElement).value).toBe(
      "",
    );
    expect((screen.getByLabelText(t("settings.providers.kindLabel")) as HTMLSelectElement).value).toBe(
      "fake",
    );
  });
});

describe("the key's round-trip", () => {
  it("shows the full key exactly once, on the create", async () => {
    api.POST.mockResolvedValue({
      data: { ...PROVIDER, id: "22222222-2222-2222-2222-222222222222", api_key: "sk-brand-new" },
      response: new Response(null, { status: 201 }),
    });
    renderSection();

    await userEvent.type(screen.getByLabelText(t("settings.providers.nameLabel")), "Neu");
    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.create") }));

    const notice = await screen.findByRole("status");
    expect(notice.textContent).toContain("sk-brand-new");

    // Dismissed, the key never exists again anywhere on the page.
    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.keyOnceDone") }));
    expect(screen.queryByText(/sk-brand-new/)).toBeNull();
  });

  it("opens the edit with an empty key field that means keep", async () => {
    renderSection();

    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.edit") }));

    const key = screen.getByLabelText(t("settings.providers.apiKeyLabel")) as HTMLInputElement;
    expect(key.value).toBe("");
    expect(screen.getByText(t("settings.providers.apiKeyHint"))).toBeTruthy();
    // The kind is what the provider is: not editable.
    expect((screen.getByLabelText(t("settings.providers.kindLabel")) as HTMLSelectElement).disabled).toBe(
      true,
    );
  });
});

describe("a provider the server refuses to delete", () => {
  it("names the models still pointed at it", async () => {
    api.DELETE.mockResolvedValue({
      data: undefined,
      response: new Response(null, { status: 409 }),
    });
    renderSection();

    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.delete") }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("settings.providers.errorInUse"));
  });

  it("names a delete that never reaches the service", async () => {
    api.DELETE.mockRejectedValue(new TypeError("Failed to fetch"));
    renderSection();

    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.delete") }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("settings.providers.errorDelete"));
  });
});

describe("model discovery on the row", () => {
  it("lists the ids, and a picked one is handed to the model form", async () => {
    const onModelSeed = vi.fn();
    api.GET.mockResolvedValue({ data: ["vendor-max", "vendor-mini"], response: ok() });
    render(
      <ProvidersSection
        providers={[PROVIDER]}
        presets={PRESETS}
        reload={async () => {}}
        guard={NO_GUARD}
        onDirty={() => {}}
        onModelSeed={onModelSeed}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.discover") }));
    expect(await screen.findByText(t("settings.providers.models"))).toBeTruthy();

    // The picked id travels with its provider: the model form is pointed at
    // both, the way the panel's seed lands there.
    await userEvent.click(screen.getByRole("button", { name: "vendor-mini" }));
    expect(onModelSeed).toHaveBeenCalledWith(PROVIDER.id, "vendor-mini");
  });

  it("stacks the label above the chips, and a chip wraps its own id", async () => {
    // A vendor id can be longer than a 360 px screen: the chip carries
    // `max-w-full break-all` so the id breaks inside its button instead of
    // pushing the panel wider, and the Notice stacks (`flex-col
    // items-start` beats its own flex row) so the label stands above.
    api.GET.mockResolvedValue({ data: ["vendor-max"], response: ok() });
    render(
      <ProvidersSection
        providers={[PROVIDER]}
        presets={PRESETS}
        reload={async () => {}}
        guard={NO_GUARD}
        onDirty={() => {}}
        onModelSeed={() => {}}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.discover") }));
    const notice = await screen.findByRole("status");
    expect(notice.className).toContain("flex-col");
    expect(notice.className).toContain("items-start");

    const chip = screen.getByRole("button", { name: "vendor-max" });
    expect(chip.className).toContain("max-w-full");
    expect(chip.className).toContain("break-all");
  });

  it("says there are none when the endpoint lists no models", async () => {
    api.GET.mockResolvedValue({ data: [], response: ok() });
    render(
      <ProvidersSection
        providers={[PROVIDER]}
        presets={PRESETS}
        reload={async () => {}}
        guard={NO_GUARD}
        onDirty={() => {}}
        onModelSeed={() => {}}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.discover") }));
    const notice = await screen.findByRole("status");
    expect(notice.textContent).toContain(t("settings.providers.modelsEmpty"));
    // A bare heading is not an answer: neither the label nor a chip shows.
    expect(screen.queryByText(t("settings.providers.models"))).toBeNull();
  });

  it("offers discovery on the anthropic kind too — its wire answers a list", () => {
    render(
      <ProvidersSection
        providers={[{ ...PROVIDER, kind: "anthropic" }]}
        presets={PRESETS}
        reload={async () => {}}
        guard={NO_GUARD}
        onDirty={() => {}}
        onModelSeed={() => {}}
      />,
    );

    expect(
      screen.getByRole("button", { name: t("settings.providers.discover") }),
    ).toBeTruthy();
  });

  it("offers no discovery on a fake — there is no endpoint to ask", () => {
    render(
      <ProvidersSection
        providers={[{ ...PROVIDER, kind: "fake", base_url: null }]}
        presets={PRESETS}
        reload={async () => {}}
        guard={NO_GUARD}
        onDirty={() => {}}
        onModelSeed={() => {}}
      />,
    );

    expect(screen.queryByRole("button", { name: t("settings.providers.discover") })).toBeNull();
  });

  it("names the failure while the endpoint cannot be asked", async () => {
    api.GET.mockResolvedValue({
      error: { detail: "model discovery failed" },
      response: new Response(null, { status: 502 }),
    });
    renderSection();

    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.discover") }));

    const notice = await screen.findByRole("status");
    expect(notice.textContent).toContain(t("settings.providers.errorModels"));
  });

  it("names a discovery that never reaches the service", async () => {
    api.GET.mockRejectedValue(new TypeError("Failed to fetch"));
    renderSection();

    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.discover") }));

    const notice = await screen.findByRole("status");
    expect(notice.textContent).toContain(t("settings.providers.errorModels"));
  });
});

describe("the dirty form", () => {
  it("asks before Cancel throws typed values away, and Stay keeps them", async () => {
    const ask = vi.fn(async () => false);
    render(
      <ProvidersSection
        providers={[PROVIDER]}
        presets={null}
        reload={async () => {}}
        guard={{ dirty: true, ask }}
        onDirty={() => {}}
        onModelSeed={() => {}}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.edit") }));
    const name = screen.getByLabelText(t("settings.providers.nameLabel")) as HTMLInputElement;
    await userEvent.type(name, "Neu");

    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.cancel") }));
    expect(ask).toHaveBeenCalled();
    // The ask refused: the typed value ("Neu" after the row's own "Vendor")
    // stays in the form.
    expect((screen.getByLabelText(t("settings.providers.nameLabel")) as HTMLInputElement).value).toBe(
      "VendorNeu",
    );
  });
});
