// @vitest-environment jsdom
/**
 * The switcher's refused write: the display goes back to the locale that is
 * actually stored, and the failure speaks below the label-and-control row —
 * not inside it, where a padded block in the bar's non-wrapping row would
 * overflow a narrow screen.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "../lib/api/client";
import { t } from "../lib/i18n";
import { applyLocale, chosenLocale } from "../lib/locale";
import { LanguageSwitcher } from "./LanguageSwitcher";

vi.mock("../lib/api/client", () => ({
  client: { PATCH: vi.fn() },
}));

const patch = client.PATCH as unknown as ReturnType<typeof vi.fn>;

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  // The locale is global state; the test must not leak it.
  applyLocale(null);
});

describe("LanguageSwitcher's refused write", () => {
  it("restores the stored locale and names the failure below the row", async () => {
    applyLocale("de");
    patch.mockRejectedValue(new Error("the service is down"));
    render(<LanguageSwitcher />);

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "en" } });
    await screen.findByRole("alert");

    // The write did not happen, so neither the store nor the control
    // pretends it did.
    expect(chosenLocale()).toBe("de");
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("de");

    // The failure speaks below the row: its parent is the stacked root,
    // not the inline label-and-control row.
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toBe(t("settings.errorSave"));
    expect(alert.parentElement?.className).toContain("flex-col");
  });
});
