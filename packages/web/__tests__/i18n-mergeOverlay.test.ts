/**
 * Unit tests for `mergeOverlay` — the formality overlay deep-merge helper
 * (Feature Spec I-Copy-001).
 *
 * Deep-merge correctness is the main technical risk of the overlay approach:
 * base namespaces contain nested objects (`settings.themes`), and the loader
 * caches imported modules (so the merge must not mutate its inputs).
 */

import { describe, expect, it } from "vitest";
import { mergeOverlay } from "@/lib/i18n/mergeOverlay";

describe("mergeOverlay", () => {
  it("overrides flat leaf keys and preserves base-only leaves", () => {
    const merged = mergeOverlay({ a: "1", b: "2" }, { b: "B!" });
    expect(merged).toEqual({ a: "1", b: "B!" });
  });

  it("recurses into nested objects, overriding only the targeted leaf (the critical deep-merge case)", () => {
    // Mirrors the real de/settings.json shape: themes: { light, dark, system }.
    // `mergeOverlay` honestly returns `Record<string, unknown>` — the overlay may
    // ADD keys absent from the base, so a generic `<T>` return would be unsound.
    // We know the exact shape here, so narrow once at the binding to assert on it
    // (test-side typing concern; the merge signature stays honest).
    type SettingsTree = {
      title: string;
      themes: { light: string; dark: string; system: string };
    };
    const base = {
      title: "Einstellungen",
      themes: { light: "Hell", dark: "Dunkel", system: "System" },
    };
    const merged = mergeOverlay(base, { themes: { system: "Systemdesign" } }) as SettingsTree;

    // The targeted leaf is overridden…
    expect(merged.themes.system).toBe("Systemdesign");
    // …sibling leaves are preserved…
    expect(merged.themes.light).toBe("Hell");
    expect(merged.themes.dark).toBe("Dunkel");
    // …and unrelated top-level keys are untouched.
    expect(merged.title).toBe("Einstellungen");
  });

  it("overlay wins on direct conflict", () => {
    expect(mergeOverlay({ k: "base" }, { k: "overlay" })).toEqual({ k: "overlay" });
  });

  it("empty overlay returns an equivalent tree (no crash, base preserved)", () => {
    const base = { a: { b: "c" } };
    expect(mergeOverlay(base, {})).toEqual(base);
  });

  it("does not mutate the base object (the loader caches imported modules)", () => {
    const base = { themes: { light: "Hell", dark: "Dunkel" } };
    mergeOverlay(base, { themes: { light: "LIGHT" } });

    expect(base.themes.light).toBe("Hell");
    expect(base.themes.dark).toBe("Dunkel");
  });

  it("does not mutate the overlay object", () => {
    const overlay = { themes: { light: "LIGHT" } };
    mergeOverlay({ themes: { light: "Hell", dark: "Dunkel" } }, overlay);

    expect(overlay.themes).toEqual({ light: "LIGHT" });
  });

  it("adds an overlay key absent from base without crashing (additive)", () => {
    expect(mergeOverlay({ a: "1" }, { newKey: "x" })).toEqual({ a: "1", newKey: "x" });
  });

  it("replaces (does not recurse into) a non-object base value with an object overlay", () => {
    // Defensive: type-mismatched shapes must not corrupt — overlay wins wholesale.
    expect(mergeOverlay({ k: "str" }, { k: { nested: "v" } })).toEqual({ k: { nested: "v" } });
  });

  it("treats arrays as leaf values (overlay replaces wholesale, no index merge)", () => {
    const base = { list: ["a", "b"] };
    expect(mergeOverlay(base, { list: ["x"] })).toEqual({ list: ["x"] });
  });
});
