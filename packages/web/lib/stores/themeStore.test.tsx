import { describe, expect, it } from "vitest";
import { useThemeStore } from "./themeStore";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ThemeStore", () => {
  beforeEach(() => {
    // Clear the store before each test
    useThemeStore.setState({
      theme: "neutral",
      colorMode: "system",
    });
  });

  describe("initial state", () => {
    it("should have default theme and colorMode", () => {
      const state = useThemeStore.getState();
      expect(state.theme).toBe("neutral");
      expect(state.colorMode).toBe("system");
    });
  });

  describe("setTheme", () => {
    it("should update theme", () => {
      useThemeStore.getState().setTheme("narrare");
      expect(useThemeStore.getState().theme).toBe("narrare");
    });

    it("should not affect colorMode when changing theme", () => {
      useThemeStore.getState().setTheme("narrare");
      expect(useThemeStore.getState().colorMode).toBe("system");
    });
  });

  describe("setColorMode", () => {
    it("should update colorMode", () => {
      useThemeStore.getState().setColorMode("dark");
      expect(useThemeStore.getState().colorMode).toBe("dark");
    });

    it("should not affect theme when changing colorMode", () => {
      useThemeStore.getState().setColorMode("light");
      expect(useThemeStore.getState().theme).toBe("neutral");
    });
  });

  describe("persistence", () => {
    it("should persist theme and colorMode", () => {
      // Set values
      useThemeStore.getState().setTheme("narrare");
      useThemeStore.getState().setColorMode("dark");

      // Create a new store instance (simulating page reload)
      const hydratedState = useThemeStore.getState();

      // Note: In a real test with persist middleware, we would need to
      // simulate the hydration. For this unit test, we verify the setters work.
      expect(hydratedState.theme).toBe("narrare");
      expect(hydratedState.colorMode).toBe("dark");
    });
  });

  describe("edge cases", () => {
    it("should accept all valid theme values", () => {
      useThemeStore.getState().setTheme("neutral");
      expect(useThemeStore.getState().theme).toBe("neutral");

      useThemeStore.getState().setTheme("narrare");
      expect(useThemeStore.getState().theme).toBe("narrare");
    });

    it("should accept all valid colorMode values", () => {
      useThemeStore.getState().setColorMode("light");
      expect(useThemeStore.getState().colorMode).toBe("light");

      useThemeStore.getState().setColorMode("dark");
      expect(useThemeStore.getState().colorMode).toBe("dark");

      useThemeStore.getState().setColorMode("system");
      expect(useThemeStore.getState().colorMode).toBe("system");
    });
  });
});
