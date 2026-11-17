/**
 * The locale number-words util (W4 Task 11): the workspace's scene header
 * writes its ordinals out — „Kapitel Eins · Szene Zwei" — in the catalog's
 * three languages. The bound is twenty: a chapter or scene beyond it keeps
 * the digit, never a guessed word, and so does every value that is not a
 * positive integer (zero, negatives, fractions, NaN, infinities).
 */
import { describe, expect, it } from "vitest";

import { NUMBER_WORD_BOUND, numberWord } from "./numberWords";

describe("numberWord", () => {
  it("writes the German cardinals one to twenty", () => {
    const words = [
      "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn",
      "elf", "zwölf", "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn",
      "achtzehn", "neunzehn", "zwanzig",
    ];
    words.forEach((word, at) => {
      expect(numberWord(at + 1, "de")).toBe(word);
    });
  });

  it("writes the English cardinals one to twenty", () => {
    const words = [
      "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
      "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
      "eighteen", "nineteen", "twenty",
    ];
    words.forEach((word, at) => {
      expect(numberWord(at + 1, "en")).toBe(word);
    });
  });

  it("writes the French cardinals one to twenty", () => {
    const words = [
      "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
      "onze", "douze", "treize", "quatorze", "quinze", "seize", "dix-sept", "dix-huit",
      "dix-neuf", "vingt",
    ];
    words.forEach((word, at) => {
      expect(numberWord(at + 1, "fr")).toBe(word);
    });
  });

  it("the bound is twenty — the last written word, the first digit after", () => {
    expect(NUMBER_WORD_BOUND).toBe(20);
    for (const locale of ["de", "en", "fr"] as const) {
      expect(numberWord(20, locale)).not.toBe("20");
      expect(numberWord(21, locale)).toBe("21");
      expect(numberWord(100, locale)).toBe("100");
    }
  });

  it("falls back to the digit outside the positive integers", () => {
    for (const locale of ["de", "en", "fr"] as const) {
      expect(numberWord(0, locale)).toBe("0");
      expect(numberWord(-1, locale)).toBe("-1");
      expect(numberWord(2.5, locale)).toBe("2.5");
      expect(numberWord(Number.NaN, locale)).toBe("NaN");
      expect(numberWord(Number.POSITIVE_INFINITY, locale)).toBe("Infinity");
    }
  });
});
