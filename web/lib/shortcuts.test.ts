// @vitest-environment jsdom
/**
 * The shortcut registry is shell data: one list of the bindings the app
 * really answers to — each with a catalog label, a keycap per platform and
 * the scope it applies in. No aspirational entries: every id below names a
 * listener that exists in the code (the report in the task's doc names the
 * file each came from).
 */
import { afterEach, describe, expect, it } from "vitest";

import { locales } from "./generated/catalogs";
import { t } from "./i18n";
import { applyLocale } from "./locale";
import { SHORTCUTS, shortcutKeycap } from "./shortcuts";

afterEach(() => {
  applyLocale(null);
});

describe("the shortcut registry", () => {
  it("names each binding once, with a scope the app knows", () => {
    const ids = SHORTCUTS.map((entry) => entry.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const entry of SHORTCUTS) {
      expect(["global", "editor", "workspace"]).toContain(entry.scope);
    }
  });

  it("gives every entry a label and a keycap per platform in every locale", () => {
    for (const candidate of locales) {
      applyLocale(candidate);
      for (const entry of SHORTCUTS) {
        expect(t(entry.labelKey).trim(), `${candidate}/${entry.id}/label`).not.toBe("");
        expect(t(entry.macKey).trim(), `${candidate}/${entry.id}/mac`).not.toBe("");
        expect(t(entry.otherKey).trim(), `${candidate}/${entry.id}/other`).not.toBe("");
      }
    }
  });

  it("answers the palette's key through the registry on this platform", () => {
    // jsdom's user agent is no Apple platform, so the registry's answer is
    // the other-platform keycap — the same glyph the chip and the footer
    // render.
    expect(shortcutKeycap("palette.toggle")).toBe(t("shell.paletteKeyOther"));
  });
});
