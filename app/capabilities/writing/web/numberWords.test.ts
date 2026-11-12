/**
 * The eyebrow's number words are a worded contract: the tests pin the exact
 * strings a reader sees — the brief's set per locale, plus the irregular
 * paths a table can miss (German's raised six and seven stems, French's
 * vingts and "et" forms) — the digits fallback past the bound, and the one
 * rule for input the contract does not cover.
 */
import { describe, expect, it } from "vitest";

import { chapterOrdinal } from "./numberWords";

describe("chapterOrdinal", () => {
  it("writes German 1–99 out, including the raised six and seven stems", () => {
    expect(chapterOrdinal(1, "de")).toBe("Eins");
    expect(chapterOrdinal(2, "de")).toBe("Zwei");
    expect(chapterOrdinal(3, "de")).toBe("Drei");
    expect(chapterOrdinal(11, "de")).toBe("Elf");
    expect(chapterOrdinal(13, "de")).toBe("Dreizehn");
    expect(chapterOrdinal(16, "de")).toBe("Sechzehn");
    expect(chapterOrdinal(17, "de")).toBe("Siebzehn");
    expect(chapterOrdinal(21, "de")).toBe("Einundzwanzig");
    expect(chapterOrdinal(27, "de")).toBe("Siebenundzwanzig");
    expect(chapterOrdinal(30, "de")).toBe("Dreißig");
    expect(chapterOrdinal(66, "de")).toBe("Sechsundsechzig");
    expect(chapterOrdinal(99, "de")).toBe("Neunundneunzig");
  });

  it("writes English 1–99 out, tens and unit hyphenated", () => {
    expect(chapterOrdinal(1, "en")).toBe("One");
    expect(chapterOrdinal(2, "en")).toBe("Two");
    expect(chapterOrdinal(3, "en")).toBe("Three");
    expect(chapterOrdinal(11, "en")).toBe("Eleven");
    expect(chapterOrdinal(13, "en")).toBe("Thirteen");
    expect(chapterOrdinal(21, "en")).toBe("Twenty-One");
    expect(chapterOrdinal(40, "en")).toBe("Forty");
    expect(chapterOrdinal(99, "en")).toBe("Ninety-Nine");
  });

  it("writes French 1–99 out, vingts and et-forms included", () => {
    expect(chapterOrdinal(1, "fr")).toBe("Un");
    expect(chapterOrdinal(2, "fr")).toBe("Deux");
    expect(chapterOrdinal(3, "fr")).toBe("Trois");
    expect(chapterOrdinal(11, "fr")).toBe("Onze");
    expect(chapterOrdinal(13, "fr")).toBe("Treize");
    expect(chapterOrdinal(17, "fr")).toBe("Dix-Sept");
    expect(chapterOrdinal(21, "fr")).toBe("Vingt et Un");
    expect(chapterOrdinal(70, "fr")).toBe("Soixante-Dix");
    expect(chapterOrdinal(71, "fr")).toBe("Soixante et Onze");
    expect(chapterOrdinal(80, "fr")).toBe("Quatre-Vingts");
    expect(chapterOrdinal(81, "fr")).toBe("Quatre-Vingt-Un");
    expect(chapterOrdinal(91, "fr")).toBe("Quatre-Vingt-Onze");
    expect(chapterOrdinal(99, "fr")).toBe("Quatre-Vingt-Dix-Neuf");
  });

  it("writes every number 1–99 in every locale: words only, led by a capital", () => {
    for (const locale of ["de", "en", "fr"] as const) {
      for (let n = 1; n <= 99; n++) {
        const word = chapterOrdinal(n, locale);
        expect(word, `${locale} ${n}`).toMatch(/^[A-ZÀ-ÖØ-Þ]/u);
        expect(word, `${locale} ${n}`).not.toMatch(/\d/u);
      }
    }
  });

  it("renders the bound as digits: zero and everything past ninety-nine", () => {
    expect(chapterOrdinal(0, "en")).toBe("0");
    expect(chapterOrdinal(100, "de")).toBe("100");
    expect(chapterOrdinal(237, "fr")).toBe("237");
  });

  it("rejects a negative or fractional number — clamping would mislabel a chapter", () => {
    expect(() => chapterOrdinal(-1, "en")).toThrow(RangeError);
    expect(() => chapterOrdinal(7.5, "de")).toThrow(RangeError);
  });
});
