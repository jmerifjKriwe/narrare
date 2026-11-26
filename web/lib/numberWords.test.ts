/**
 * The locale number-words util (W4 Task 11): the workspace's scene header
 * writes its ordinals out — „Kapitel Eins · Szene Zwei" — in the active
 * language's catalog. The bound is twenty: a chapter or scene beyond it keeps
 * the digit, never a guessed word, and so does every value that is not a
 * positive integer.
 */
import { describe, expect, it } from "vitest";

import { applyLocale } from "./locale";
import { capitalizedWord, numberWord } from "./numberWords";

describe("numberWord", () => {
  it("writes one to twenty in the active language", () => {
    applyLocale("de");
    expect([numberWord(1), numberWord(7), numberWord(11), numberWord(20)]).toEqual([
      "eins",
      "sieben",
      "elf",
      "zwanzig",
    ]);
    applyLocale("fr");
    expect(numberWord(17)).toBe("dix-sept");
    applyLocale("en");
    expect(numberWord(11)).toBe("eleven");
  });

  it("falls back to the digit beyond twenty and for anything that is not a positive integer", () => {
    expect([numberWord(0), numberWord(21), numberWord(2.5), numberWord(-3)]).toEqual([
      "0",
      "21",
      "2.5",
      "-3",
    ]);
  });

  it("capitalizes the first letter only", () => {
    applyLocale("de");
    expect(capitalizedWord(1)).toBe("Eins");
    applyLocale("fr");
    expect(capitalizedWord(17)).toBe("Dix-sept");
  });
});
