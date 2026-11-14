import IntlMessageFormat from "intl-messageformat";
import { afterEach, describe, expect, it, vi } from "vitest";

import { applyFormality } from "./formality";
import { catalogs, locales } from "./generated/catalogs";
import { overlays } from "./generated/overlays";
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
    // shell.paletteOpen is the one central message with a parameter while
    // the rebuilt screens bring their copy back. The expected value comes
    // from the active catalog, so the test survives a locale change; a
    // formatter that never ran would return the raw "{key}".
    const message = catalogs[activeLocale()]["shell.paletteOpen"];
    expect(t("shell.paletteOpen", { key: "⌘K" })).toBe(message.replace("{key}", "⌘K"));
    expect(t("shell.paletteOpen", { key: "⌘K" })).not.toContain("{");
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

describe("the formal register", () => {
  afterEach(() => {
    applyFormality("informal");
    applyLocale("en");
  });

  // The end-to-end overlay assertions — a formal variant rendered beside
  // its informal base — left with the capability catalogs that carried
  // their strings; the demolition leaves no live overlay key. The gates
  // below keep the register's machinery pinned over the keys that remain,
  // and the end-to-end form returns with the rebuilt copy (W2).

  it("falls through to the base where the overlay is silent", () => {
    applyLocale("de");
    applyFormality("formal");

    expect(t("nav.back")).toBe("Alle Romane");
  });

  it("leaves English unchanged", () => {
    applyLocale("en");
    applyFormality("formal");

    expect(t("nav.back")).toBe(catalogs.en["nav.back"]);
  });

  it("parses every overlay message", () => {
    for (const [locale, overlay] of Object.entries(overlays)) {
      if (overlay === undefined) continue;
      for (const [key, message] of Object.entries(overlay)) {
        expect(
          () => new IntlMessageFormat(message, locale),
          `${locale}/${key}`,
        ).not.toThrow();
      }
    }
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
    expect(t("nav.back")).toBe("Alle Romane");
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
