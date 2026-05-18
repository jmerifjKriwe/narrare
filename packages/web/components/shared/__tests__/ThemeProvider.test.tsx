import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider } from "@/components/shared/ThemeProvider";

// We need to mock themeStore with a controllable implementation
const { mockThemeStore } = vi.hoisted(() => ({
  mockThemeStore: vi.fn(),
}));

vi.mock("@/lib/stores/themeStore", () => ({
  useThemeStore: mockThemeStore,
}));

// Mock window.matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

function mockTheme(theme: string, colorMode: string) {
  mockThemeStore.mockImplementation(
    (selector?: (s: Record<string, unknown>) => unknown) => {
      const state = { theme, colorMode };
      return selector ? selector(state) : state;
    },
  );
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    mockTheme("neutral", "light");
  });

  afterEach(() => {
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.classList.remove("dark");
    vi.clearAllMocks();
  });

  it("renders nothing", () => {
    const { container } = render(<ThemeProvider />);
    expect(container.firstChild).toBeNull();
  });

  it("applies theme from store after mounting", () => {
    mockTheme("narrare", "light");
    render(<ThemeProvider />);
    expect(document.documentElement.getAttribute("data-theme")).toBe("narrare");
  });

  it("adds dark class when colorMode is dark", () => {
    mockTheme("neutral", "dark");
    render(<ThemeProvider />);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("removes dark class when colorMode is light", () => {
    document.documentElement.classList.add("dark");
    mockTheme("neutral", "light");
    render(<ThemeProvider />);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
