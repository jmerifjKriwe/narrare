/**
 * Tests for LanguageSwitcher component (auth pages)
 *
 * Verifies: rendering, locale display, cookie setting on change.
 */

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LanguageSwitcher } from "@/components/auth/LanguageSwitcher";

// Mocks are provided globally by setupTests.ts (next/navigation, next-intl)
// We override useLocale and useRouter locally for these tests

const mockRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: mockRefresh,
  }),
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/login",
}));

vi.mock("next-intl", () => ({
  useLocale: () => "en",
  useTranslations: () => (key: string) => key,
}));

describe("LanguageSwitcher", () => {
  afterEach(() => {
    cleanup();
    mockRefresh.mockClear();
  });

  it("renders a select with three language options", () => {
    render(<LanguageSwitcher />);
    const select = screen.getByLabelText("Language");
    expect(select).toBeInTheDocument();
    expect(select).toHaveValue("en");

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(3);
    expect(options[0]).toHaveValue("de");
    expect(options[1]).toHaveValue("en");
    expect(options[2]).toHaveValue("fr");
  });

  it("sets NEXT_LOCALE cookie and calls router.refresh on change", async () => {
    const user = userEvent.setup();
    render(<LanguageSwitcher />);

    const select = screen.getByLabelText("Language");
    await user.selectOptions(select, "de");

    expect(document.cookie).toContain("NEXT_LOCALE=de");
    expect(mockRefresh).toHaveBeenCalledTimes(1);
  });

  it("switches to French and refreshes router", async () => {
    const user = userEvent.setup();
    render(<LanguageSwitcher />);

    const select = screen.getByLabelText("Language");
    await user.selectOptions(select, "fr");

    // jsdom's document.cookie doesn't expose attributes (max-age, path, etc.)
    // but we can verify the value was set
    expect(document.cookie).toContain("NEXT_LOCALE=fr");
    expect(mockRefresh).toHaveBeenCalled();
  });
});
