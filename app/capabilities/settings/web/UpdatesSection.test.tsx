// @vitest-environment jsdom
/**
 * The Updates section (Task 3): the update check's interval, small and local.
 *
 * The section is not a second dirty form — one field, the save enabled only
 * when the answer is valid and differs from the stored one, the saved line
 * and the retryable refusal line. The write rides the settings page's own
 * PATCH through `useUpdateSettings`, the locale always carried (the schema's
 * rule), so the section never invents a second settings contract.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, configure, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { UpdatesSection } from "./UpdatesSection";

const de = catalogs.de;
const api = client as unknown as Record<"PATCH", ReturnType<typeof vi.fn>>;

configure({ asyncUtilTimeout: 5000 });

function ok(): Response {
  return new Response(null, { status: 200 });
}

function row(interval: number | null = 7) {
  return { locale: "de" as string | null, update_check_interval_days: interval };
}

function renderSection(interval: number | null = 7) {
  render(
    <QueryClientProvider client={queryClient}>
      <UpdatesSection row={row(interval)} />
    </QueryClientProvider>,
  );
}

function intervalInput(): HTMLInputElement {
  return screen.getByLabelText(de["settings.update.label"]) as HTMLInputElement;
}

function saveButton(): HTMLButtonElement {
  return screen.getByRole("button", { name: de["settings.update.save"] }) as HTMLButtonElement;
}

beforeEach(() => {
  api.PATCH.mockReset();
  api.PATCH.mockResolvedValue({ data: {}, response: ok() });
  applyLocale("de");
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  applyLocale(null);
});

describe("the Updates section", () => {
  it("renders the stored interval and a pristine save rests", () => {
    renderSection(7);
    expect(intervalInput().value).toBe("7");
    expect(saveButton().disabled).toBe(true);
    fireEvent.click(saveButton());
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it("an unset row opens on the product default, not an empty field", () => {
    renderSection(null);
    expect(intervalInput().value).toBe("7");
    expect(saveButton().disabled).toBe(true);
  });

  it("a changed interval rides the settings PATCH and the saved line answers", async () => {
    renderSection(7);

    fireEvent.change(intervalInput(), { target: { value: "3" } });
    expect(saveButton().disabled).toBe(false);
    fireEvent.click(saveButton());

    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][0]).toBe("/api/settings");
    expect(api.PATCH.mock.calls[0][1].body).toEqual({
      locale: "de",
      update_check_interval_days: 3,
    });
    expect(await screen.findByText(de["settings.update.saved"])).toBeTruthy();
    // The accepted answer is no change while the rendered row is still the
    // pre-write one: a second identical PATCH cannot fire in that window.
    expect(saveButton().disabled).toBe(true);
    fireEvent.click(saveButton());
    expect(api.PATCH).toHaveBeenCalledTimes(1);
  });

  it("an out-of-range interval disables the save and names itself", () => {
    renderSection(7);

    for (const value of ["0", "366", ""]) {
      fireEvent.change(intervalInput(), { target: { value } });
      expect(saveButton().disabled).toBe(true);
    }
    expect(screen.getByText(de["settings.update.invalid"])).toBeTruthy();
    fireEvent.click(saveButton());
    expect(api.PATCH).not.toHaveBeenCalled();

    // The bounds themselves are valid answers, and the refusal line retires.
    for (const value of ["1", "365"]) {
      fireEvent.change(intervalInput(), { target: { value } });
      expect(saveButton().disabled).toBe(false);
    }
    expect(screen.queryByText(de["settings.update.invalid"])).toBeNull();
  });

  it("a refused save keeps the answer and the retry re-runs the ask", async () => {
    let refuse = true;
    api.PATCH.mockImplementation(async () => {
      if (refuse) return { data: undefined, response: new Response(null, { status: 500 }) };
      return { data: {}, response: ok() };
    });
    renderSection(7);

    fireEvent.change(intervalInput(), { target: { value: "3" } });
    fireEvent.click(saveButton());

    expect(await screen.findByText(de["settings.update.error"])).toBeTruthy();
    expect(intervalInput().value).toBe("3");

    refuse = false;
    fireEvent.click(screen.getByRole("button", { name: de["settings.retry"] }));
    await waitFor(() => expect(screen.queryByText(de["settings.update.error"])).toBeNull());
    expect(await screen.findByText(de["settings.update.saved"])).toBeTruthy();
  });
});
