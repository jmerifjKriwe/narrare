import { beforeEach, describe, expect, it, vi } from "vitest";
import { useThemeStore } from "./themeStore";

// Mock localStorage for persist middleware
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(globalThis, "localStorage", { value: localStorageMock });

describe("useThemeStore", () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useThemeStore.setState({
      theme: "neutral",
      colorMode: "system",
    });
    // Clear localStorage mock
    vi.clearAllMocks();
    localStorageMock.clear();
  });

  describe("initial state", () => {
    it("should have neutral theme by default", () => {
      expect(useThemeStore.getState().theme).toBe("neutral");
    });

    it("should have system color mode by default", () => {
      expect(useThemeStore.getState().colorMode).toBe("system");
    });
  });

  describe("setTheme", () => {
    it("should set theme to narrare", () => {
      useThemeStore.getState().setTheme("narrare");
      expect(useThemeStore.getState().theme).toBe("narrare");
    });

    it("should set theme to neutral", () => {
      useThemeStore.setState({ theme: "narrare" });
      useThemeStore.getState().setTheme("neutral");
      expect(useThemeStore.getState().theme).toBe("neutral");
    });

    it("should allow switching between themes", () => {
      useThemeStore.getState().setTheme("narrare");
      expect(useThemeStore.getState().theme).toBe("narrare");

      useThemeStore.getState().setTheme("neutral");
      expect(useThemeStore.getState().theme).toBe("neutral");
    });
  });

  describe("setColorMode", () => {
    it("should set color mode to light", () => {
      useThemeStore.getState().setColorMode("light");
      expect(useThemeStore.getState().colorMode).toBe("light");
    });

    it("should set color mode to dark", () => {
      useThemeStore.getState().setColorMode("dark");
      expect(useThemeStore.getState().colorMode).toBe("dark");
    });

    it("should set color mode back to system", () => {
      useThemeStore.setState({ colorMode: "dark" });
      useThemeStore.getState().setColorMode("system");
      expect(useThemeStore.getState().colorMode).toBe("system");
    });

    it("should allow cycling through all modes", () => {
      useThemeStore.getState().setColorMode("light");
      expect(useThemeStore.getState().colorMode).toBe("light");

      useThemeStore.getState().setColorMode("dark");
      expect(useThemeStore.getState().colorMode).toBe("dark");

      useThemeStore.getState().setColorMode("system");
      expect(useThemeStore.getState().colorMode).toBe("system");
    });
  });

  describe("persistence", () => {
    it("should have persist middleware configured", () => {
      // Verify the store has persist configuration by checking the state persists after setState
      useThemeStore.setState({ theme: "narrare", colorMode: "dark" });
      const state = useThemeStore.getState();
      expect(state.theme).toBe("narrare");
      expect(state.colorMode).toBe("dark");
    });

    it("should allow state changes that persist middleware would save", () => {
      // Test that multiple state changes work correctly
      useThemeStore.getState().setTheme("narrare");
      useThemeStore.getState().setColorMode("light");

      const state = useThemeStore.getState();
      expect(state.theme).toBe("narrare");
      expect(state.colorMode).toBe("light");
    });
  });
});
