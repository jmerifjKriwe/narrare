// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { applyTheme, adoptServerTheme, THEME_HINT } from "./theme";

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
  localStorage.clear();
});

describe("applyTheme", () => {
  it("marks the document and remembers the choice", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(THEME_HINT)).toBe("dark");
  });

  it("clears both when the system decides", () => {
    applyTheme("light");
    applyTheme(null);
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    expect(localStorage.getItem(THEME_HINT)).toBeNull();
  });
});

describe("adoptServerTheme", () => {
  it("takes the two stored values and treats anything else as the system", () => {
    adoptServerTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    adoptServerTheme("sepia");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });
});
