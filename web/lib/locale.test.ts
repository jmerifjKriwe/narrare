import { afterEach, describe, expect, it, vi } from "vitest";

import { formattingLocale } from "./format";
import { activeLocale, applyLocale, matchLocale, resolveLocale } from "./locale";

/**
 * Tag resolution against the real registry. A stubbed browser makes the
 * regional choice testable on any machine: the suite must not depend on
 * where it runs (`web/lib/i18n.test.ts`'s own harness).
 */
function browserSpeaks(languages: string[]): void {
  vi.stubGlobal("navigator", { languages, language: languages[0] });
}

afterEach(() => {
  vi.unstubAllGlobals();
  applyLocale("en");
});

describe("the tag resolution", () => {
  it("maps a regional tag onto its language and keeps the region for formatting", () => {
    expect(resolveLocale("de-AT")).toEqual({ catalog: "de", formatLocale: "de-AT" });
  });

  it("resolves an exact code to itself", () => {
    expect(resolveLocale("fr")).toEqual({ catalog: "fr", formatLocale: "fr" });
  });

  it.each(["tlh", "tlh-AA", "", "not a tag!", null, undefined])(
    "resolves %s to the source language without throwing",
    (tag) => {
      expect(matchLocale(tag)).toBeNull();
      expect(resolveLocale(tag)).toEqual({ catalog: "en", formatLocale: "en" });
    },
  );

  it("matches a known language whose region is unknown", () => {
    expect(matchLocale("fr-CA")).toBe("fr");
  });

  it("formats a chosen language with the browser's region when the browser speaks it", () => {
    browserSpeaks(["de-AT", "de"]);
    applyLocale("de");
    expect(activeLocale()).toBe("de");
    expect(formattingLocale()).toBe("de-AT");
    applyLocale("fr");
    expect(formattingLocale()).toBe("fr");
  });

  it("keeps the browser's own tag when nobody chose", () => {
    browserSpeaks(["de-AT"]);
    applyLocale(null);
    expect(formattingLocale()).toBe("de-AT");
  });
});
