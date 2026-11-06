// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { applyTheme, THEME_HINT } from "./theme";

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
