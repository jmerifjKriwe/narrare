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
