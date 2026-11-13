// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { activeLocale, adoptServerLocale, applyLocale } from "./locale";

/**
 * The document-language contract. The prose sets justified with
 * `hyphens: auto`, and hyphenation — like screen readers — reads
 * `html lang`; the store owns that attribute, so this is where the pin
 * lives. (i18n.test.ts keeps node semantics; the document needs jsdom.)
 */

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.lang = "en";
});

describe("the document's language", () => {
  // A stubbed browser makes the precedence testable on any machine.
  function browserSpeaks(languages: string[]): void {
    vi.stubGlobal("navigator", { languages, language: languages[0] });
  }

  it("follows the locale on every adoption — boot and switcher alike", () => {
    browserSpeaks(["fr-FR"]);
    adoptServerLocale("de");
    expect(activeLocale()).toBe("de");
    expect(document.documentElement.lang).toBe("de");

    applyLocale("fr");
    expect(document.documentElement.lang).toBe("fr");
  });

  it("lands on the fallback too, never on the static pre-boot default", () => {
    // index.html ships lang="en"; a browser speaking none of the catalog
    // still re-inks the attribute through the store, so the rendered
    // catalog and the document language cannot disagree.
    browserSpeaks(["ja-JP"]);
    adoptServerLocale(null);
    expect(activeLocale()).toBe("en");
    expect(document.documentElement.lang).toBe("en");
  });
});
