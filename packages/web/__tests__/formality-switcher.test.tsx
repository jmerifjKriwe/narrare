/**
 * Tests for FormalitySwitcher component (Feature Spec I-Copy-001).
 *
 * Mirrors language-switcher.test.tsx: verifies rendering, the two register
 * options, cookie setting + router.refresh on change, and that the control is
 * hidden for en (no du/Sie distinction).
 */

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FormalitySwitcher } from "@/components/auth/FormalitySwitcher";

// Mocks are provided globally by setupTests.ts. We override useLocale and
// useRouter locally; `currentLocale` is mutable so the "hidden for en" case
// can switch it within the same describe.

let currentLocale = "de";
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
  useLocale: () => currentLocale,
  useTranslations: () => (key: string) => key,
}));

function clearFormalityCookie() {
  // biome-ignore lint/suspicious/noDocumentCookie: test cleanup — clears the cookie between cases
  document.cookie = "NEXT_FORMALITY=;path=/;max-age=0";
}

describe("FormalitySwitcher", () => {
  afterEach(() => {
    cleanup();
    mockRefresh.mockClear();
    clearFormalityCookie();
    currentLocale = "de";
  });

  it("renders a select with informal/formal options, defaulting to informal", () => {
    render(<FormalitySwitcher />);
    const select = screen.getByLabelText("Anrede");
    expect(select).toBeInTheDocument();
    expect(select).toHaveValue("informal");

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveValue("informal");
    expect(options[1]).toHaveValue("formal");
  });

  it("sets NEXT_FORMALITY cookie and calls router.refresh on change", async () => {
    const user = userEvent.setup();
    render(<FormalitySwitcher />);

    await user.selectOptions(screen.getByLabelText("Anrede"), "formal");

    // jsdom's document.cookie doesn't expose attributes (max-age, path, …),
    // but the value is verifiable.
    expect(document.cookie).toContain("NEXT_FORMALITY=formal");
    expect(mockRefresh).toHaveBeenCalledTimes(1);
  });

  it("switches back to informal and refreshes", async () => {
    const user = userEvent.setup();
    render(<FormalitySwitcher />);

    await user.selectOptions(screen.getByLabelText("Anrede"), "formal");
    await user.selectOptions(screen.getByLabelText("Anrede"), "informal");

    expect(document.cookie).toContain("NEXT_FORMALITY=informal");
    expect(mockRefresh).toHaveBeenCalledTimes(2);
  });

  it("renders nothing when locale is en (no du/Sie distinction)", () => {
    currentLocale = "en";
    const { container } = render(<FormalitySwitcher />);
    expect(container).toBeEmptyDOMElement();
  });

  it("uses French register labels for fr", () => {
    currentLocale = "fr";
    render(<FormalitySwitcher />);
    expect(screen.getByLabelText("Formule d'adresse")).toBeInTheDocument();
    expect(screen.getByText("tu")).toBeInTheDocument();
    expect(screen.getByText("vous")).toBeInTheDocument();
  });
});
