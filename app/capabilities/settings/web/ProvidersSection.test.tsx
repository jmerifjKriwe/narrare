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

const NO_GUARD = { dirty: false, ask: async () => true };

function renderSection(): void {
  render(
    <ProvidersSection providers={[PROVIDER]} reload={async () => {}} guard={NO_GUARD} onDirty={() => {}} />,
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
  it("lists the endpoint's models where they can be seen again", async () => {
    api.GET.mockResolvedValue({ data: ["vendor-max", "vendor-mini"], response: ok() });
    renderSection();

    await userEvent.click(screen.getByRole("button", { name: t("settings.providers.discover") }));

    expect(
      await screen.findByText(t("settings.providers.models", { models: "vendor-max, vendor-mini" })),
    ).toBeTruthy();
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
});

describe("the dirty form", () => {
  it("asks before Cancel throws typed values away, and Stay keeps them", async () => {
    const ask = vi.fn(async () => false);
    render(
      <ProvidersSection providers={[PROVIDER]} reload={async () => {}} guard={{ dirty: true, ask }} onDirty={() => {}} />,
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
