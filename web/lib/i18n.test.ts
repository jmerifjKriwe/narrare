import IntlMessageFormat from "intl-messageformat";
import { afterEach, describe, expect, it, vi } from "vitest";

import { applyFormality } from "./formality";
import { catalogs, locales } from "./generated/catalogs";
import { t, type MessageKey } from "./i18n";
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

  it("fills the wizard's live counters from the active catalog", () => {
    // #849: shell.paletteOpen was a dead production key kept only as this
    // fixture — the palette is gone, and the key with it. The pin now rides
    // the wizard's own parameterized copy: the step counter and the canon
    // badge. The expected value comes from the active catalog, so the test
    // survives a locale change; a formatter that never ran would return the
    // raw "{step}".
    const counter = catalogs[activeLocale()]["setup.structure.stepOf"];
    expect(t("setup.structure.stepOf", { step: 2, total: 4 })).toBe(
      counter.replace("{step}", "2").replace("{total}", "4"),
    );
    expect(t("setup.structure.stepOf", { step: 2, total: 4 })).not.toContain("{");

    const badge = catalogs[activeLocale()]["setup.aiRules.canon.badge"];
    expect(t("setup.aiRules.canon.badge", { n: 4 })).toBe(badge.replace("{n}", "4"));
    expect(t("setup.aiRules.canon.badge", { n: 4 })).not.toContain("{");
  });

  it("quotes its apostrophes so the placeholders still fill", () => {
    // A lone ' directly before a placeholder starts an ICU quoted literal:
    // the braces print instead of the value — the English receipt's
    // regression (#847). The wizard's copy carries the shape: fr's doubled
    // apostrophe, en's doubled quotes around {title}. Every locale must
    // interpolate, never quote the placeholder away.
    const cases: { key: MessageKey; params: Record<string, string | number>; value: string }[] = [
      { key: "setup.basis.demoEyebrow", params: { n: 1 }, value: "1" },
      { key: "setup.basis.banner.title", params: { title: "Dead Signal" }, value: "Dead Signal" },
      { key: "setup.structure.banner.demoTitle", params: { title: "Dead Signal" }, value: "Dead Signal" },
    ];
    for (const candidate of locales) {
      for (const { key, params, value } of cases) {
        const rendered = String(
          new IntlMessageFormat(catalogs[candidate][key], candidate).format(params),
        );
        expect(rendered, `${candidate}/${key}`).not.toMatch(/[{}]/);
        expect(rendered, `${candidate}/${key}`).toContain(value);
      }
    }
    // The French eyebrow keeps exactly one apostrophe: '' is the escape that
    // prints a literal apostrophe in any ICU, where a lone ' starts quoted
    // text — directly before a placeholder it quotes the placeholder itself.
    const fr = String(
      new IntlMessageFormat(catalogs.fr["setup.basis.demoEyebrow"], "fr").format({ n: 1 }),
    );
    expect(fr).toBe("Modèle d'atelier 1");
    // The failure shape itself, pinned so the escape's reason stays visible:
    // a lone apostrophe directly before the placeholder quotes it — the
    // braces print instead of the value (the receipt's `'{name}'` regression).
    const broken = "Modèle d'atelier '{n}'";
    expect(String(new IntlMessageFormat(broken, "fr").format({ n: 1 }))).toContain("{n}");
  });

  it("carries the chapter count exactly once in every locale", () => {
    // The old errors.* sentences split the formatted text around the link's
    // words to make them the link; a dropped or repeated placeholder broke
    // the split (#847). The chapters plural is the live carrier of that
    // shape: the count must survive formatting exactly once — a dropped #
    // loses the number, a doubled one splits the surface at the wrong
    // occurrence — in every locale, singular and plural.
    const carriers: { key: MessageKey; params: Record<string, string | number>; count: number }[] = [
      { key: "setup.basis.demoChapters", params: { count: 1 }, count: 1 },
      { key: "setup.basis.demoChapters", params: { count: 3 }, count: 3 },
      { key: "setup.landing.meta", params: { genre: "Science Fiction", count: 3 }, count: 3 },
    ];
    for (const candidate of locales) {
      for (const { key, params, count } of carriers) {
        const formatted = String(
          new IntlMessageFormat(catalogs[candidate][key], candidate).format(params),
        );
        const occurrences = formatted.split(String(count)).length - 1;
        expect(occurrences, `${candidate}/${key} count=${count}`).toBe(1);
        expect(formatted, `${candidate}/${key}`).not.toMatch(/[{}#]/);
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

describe("the formal register", () => {
  afterEach(() => {
    applyFormality("informal");
    applyLocale("en");
  });

  // The overlay registry is empty by design: the owner chose the du register
  // for the rebuilt copy, and W2 ships no formal register. The end-to-end
  // overlay assertions — a formal variant rendered beside its informal base —
  // and the "parses every overlay message" pin left with the capability
  // catalogs that carried their strings; iterating the empty registry proved
  // nothing (#843), so the parse pin is deleted rather than kept vacuous.
  // Both return with the first formal overlay. The machinery below stays
  // pinned over the keys that remain, so the fall-through cannot rot meanwhile.

  it("falls through to the base where the overlay is silent", () => {
    applyLocale("de");
    applyFormality("formal");

    expect(t("nav.back")).toBe(catalogs.de["nav.back"]);
  });

  it("leaves English unchanged", () => {
    applyLocale("en");
    applyFormality("formal");

    expect(t("nav.back")).toBe(catalogs.en["nav.back"]);
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
    expect(t("nav.back")).toBe(catalogs.de["nav.back"]);
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
