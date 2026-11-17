/**
 * The locale number-words util (W4 Task 11): the workspace's scene header
 * writes its chapter and scene ordinals out — „Kapitel Eins · Szene Zwei" —
 * in the catalog's three languages (design §6.3). The cardinals are the
 * drafted voice: the noun carries the case, the word stays the plain
 * cardinal („Szene Zwei", not „Zweite Szene").
 *
 * The bound is twenty. Beyond it — and for every value that is not a
 * positive integer — the digit stands: a manuscript with a hundred chapters
 * reads „Kapitel 100", never a guessed word. The fallback is the honest
 * neutral, not an error: the header always names its ordinal.
 */
import type { Locale } from "./generated/catalogs";

/** The last number the util writes out; the first digit fallback is 21. */
export const NUMBER_WORD_BOUND = 20;

const WORDS: Record<Locale, readonly string[]> = {
  de: [
    "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn",
    "elf", "zwölf", "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn",
    "achtzehn", "neunzehn", "zwanzig",
  ],
  en: [
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen", "twenty",
  ],
  fr: [
    "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
    "onze", "douze", "treize", "quatorze", "quinze", "seize", "dix-sept", "dix-huit",
    "dix-neuf", "vingt",
  ],
};

/** The number as its locale's written word, or the digit when the bound or
 *  the integer rule refuses. Lowercase on purpose: the call site capitalizes
 *  where its grammar asks (the German eyebrow's „Kapitel Eins"). */
export function numberWord(value: number, locale: Locale): string {
  if (!Number.isInteger(value) || value < 1 || value > NUMBER_WORD_BOUND) {
    return String(value);
  }
  return WORDS[locale][value - 1];
}

/** The word with its first letter capitalized — the eyebrow's own case. */
export function capitalizedWord(value: number, locale: Locale): string {
  const word = numberWord(value, locale);
  return word.charAt(0).toUpperCase() + word.slice(1);
}
