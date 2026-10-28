import IntlMessageFormat from "intl-messageformat";
import { afterEach, describe, expect, it, vi } from "vitest";

import { catalogs, locales } from "./generated/catalogs";
import { t } from "./i18n";
import { activeLocale, adoptServerLocale, applyLocale } from "./locale";

/**
 * Every assertion walks the generated map, never a hand-written list of
 * languages: this file must keep passing, unchanged, when a fourth catalog
 * appears.
 */
describe("i18n catalogs", () => {
  it("carry the same keys in every locale", () => {
    const expected = Object.keys(catalogs.en).sort();
    for (const candidate of locales) {
      expect(Object.keys(catalogs[candidate]).sort(), candidate).toEqual(expected);
    }
  });

  it("have no empty strings", () => {
    for (const candidate of locales) {
      for (const [key, value] of Object.entries(catalogs[candidate])) {
        expect(value.trim(), `${candidate}/${key}`).not.toBe("");
      }
    }
  });
});

describe("ICU message format", () => {
  it("parses every message of every locale", () => {
    // A malformed plural or select is a runtime crash in the middle of a page.
    // Parsing the whole catalog turns it into a failing build.
    for (const candidate of locales) {
      for (const [key, message] of Object.entries(catalogs[candidate])) {
        expect(
          () => new IntlMessageFormat(message, candidate),
          `${candidate}/${key}`,
        ).not.toThrow();
      }
    }
  });

  it("fills a placeholder from the catalog the app actually renders", () => {
    // chapters.defaultTitle is the one message with a parameter today. The
    // expected value comes from the active catalog, so the test survives a
    // locale change; a formatter that never ran would return the raw "{n}".
    const message = catalogs[activeLocale()]["chapters.defaultTitle"];
    expect(t("chapters.defaultTitle", { n: 7 })).toBe(message.replace("{n}", "7"));
    expect(t("chapters.defaultTitle", { n: 7 })).not.toContain("{");
  });

  it("renders the receipt's conflict details, not their placeholders", () => {
    // The receipt formats each refusal with that code's `params`. A lone `'`
    // in an ICU message starts a quoted literal, so `'{name}'` prints the
    // braces instead of the name — and the English receipt did exactly that
    // while de/fr used typographic quotes. Every locale must interpolate.
    const paramsByCode: Record<string, Record<string, string>> = {
      stale_revision: {
        file_updated: "2026-01-01T00:00:00+00:00",
        stock_updated: "2026-10-28T10:00:00+00:00",
      },
      type_discrepancy: { file_type: "character", stock_type: "place" },
      edge_note_differs: { edge: "Mira -knows-> Toma" },
      edge_target_missing: { name: "Mira" },
      metadata_differs: { field: "genre" },
      position_disagree: { index_position: "4", file_position: "9" },
      unknown_type: { type: "planet" },
      ambiguous_name: { name: "Mira" },
      ambiguous_edge_end: { edge: "Mira -knows-> Toma", name: "Mira" },
    };
    const keys = Object.keys(catalogs.en).filter((key) =>
      key.startsWith("shelf.report.conflict."),
    );
    const codes = keys.map((key) => key.slice("shelf.report.conflict.".length));

    // Both directions: a catalog message with no engine code is dead, and a
    // code with no message loses its localization silently.
    expect(codes.sort()).toEqual(Object.keys(paramsByCode).sort());

    for (const key of keys) {
      const code = key.slice("shelf.report.conflict.".length);
      const params = paramsByCode[code];
      if (params === undefined) throw new Error(`no param set for ${code}`);
      for (const candidate of locales) {
        const message = catalogs[candidate][key as keyof typeof catalogs.en];
        const rendered = String(new IntlMessageFormat(message, candidate).format(params));
        expect(rendered, `${candidate}/${key}`).not.toMatch(/[{}]/);
        for (const [param, value] of Object.entries(params)) {
          expect(rendered, `${candidate}/${key}: {${param}}`).toContain(value);
        }
      }
    }
  });

  it("uses each locale's own plural rules", () => {
    const german = "{count, plural, one {# Kapitel} other {# Kapitel·n}}";
    expect(new IntlMessageFormat(german, "de").format({ count: 1 })).toBe("1 Kapitel");
    expect(new IntlMessageFormat(german, "de").format({ count: 2 })).toBe("2 Kapitel·n");

    const english = "{count, plural, one {# chapter} other {# chapters}}";
    expect(new IntlMessageFormat(english, "en").format({ count: 1 })).toBe("1 chapter");
    expect(new IntlMessageFormat(english, "en").format({ count: 0 })).toBe("0 chapters");
  });
});

describe("the active language", () => {
  // A stubbed browser makes the precedence order testable on any machine: the
  // suite must not depend on where it runs.
  function browserSpeaks(languages: string[]): void {
    vi.stubGlobal("navigator", { languages, language: languages[0] });
  }

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the stored row, not what the browser asks for", () => {
    browserSpeaks(["fr-FR"]);
    adoptServerLocale("de");

    expect(activeLocale()).toBe("de");
    expect(t("settings.language")).toBe("Sprache");
  });

  it("ignores a code the catalog does not carry", () => {
    // The API refuses these, so this is the second line: a hand-edited row or
    // an older client must not blank the interface.
    browserSpeaks(["fr-FR"]);
    adoptServerLocale("tlh");

    expect(activeLocale()).toBe("fr");
  });

  it("follows the browser when nobody chose", () => {
    browserSpeaks(["fr-CA"]);
    adoptServerLocale(null);

    // A regional tag picks its language: fr-CA is served by the fr catalog.
    expect(activeLocale()).toBe("fr");
  });

  it("falls back to the source catalog when the browser speaks none of them", () => {
    browserSpeaks(["ja-JP"]);
    adoptServerLocale(null);

    expect(activeLocale()).toBe("en");
  });

  it("returns to the browser when the stored choice is cleared", () => {
    browserSpeaks(["fr-FR"]);
    adoptServerLocale("de");
    applyLocale(null);

    expect(activeLocale()).toBe("fr");
  });
});
