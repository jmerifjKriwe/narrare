/**
 * Written-out chapter numbers for the editor's eyebrow ("Kapitel Eins"),
 * one word per chapter, in the languages the catalogs carry.
 *
 * The bound is the contract (spec D-3): only 1–99 are written out — the
 * drafts this serves never name a chapter past two digits. A whole number
 * outside that range renders as its digits ("0", "100"), so a bound miss
 * stays legible on the page instead of turning into invented words. A
 * negative or fractional argument is a caller bug and throws a
 * `RangeError`: clamping would silently mislabel a chapter.
 *
 * Each locale keeps the words its spelling rules need, and the compound
 * rule that joins them: English hyphenates tens-unit ("Twenty-One");
 * German fuses unit-and-tens into one word, with the bare "ein" stem
 * ("Einundzwanzig") and the raised stems of sechzehn and siebzehn; French
 * counts in vingts past sixty-nine and keeps the literary "et" forms
 * unhyphenated ("Vingt et Un", "Soixante et Onze"). The words arrive
 * capitalized — the eyebrow opens with them — and bare: the catalog label
 * ("Chapter", "Kapitel") is the caller's prefix.
 */

/** The languages the number words speak — the catalog's three. */
type NumberLocale = "en" | "de" | "fr";

/** English 1–19, indexed by the number; position 0 is never read. */
const EN_ONES = [
  "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
  "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
  "Seventeen", "Eighteen", "Nineteen",
];

/** English tens words, indexed by the tens digit; positions 0–1 never read. */
const EN_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"];

/** German 1–19, indexed by the number; the raised stems live spelled out. */
const DE_ONES = [
  "", "Eins", "Zwei", "Drei", "Vier", "Fünf", "Sechs", "Sieben", "Acht", "Neun",
  "Zehn", "Elf", "Zwölf", "Dreizehn", "Vierzehn", "Fünfzehn", "Sechzehn",
  "Siebzehn", "Achtzehn", "Neunzehn",
];

/**
 * German tens words, indexed by the tens digit, lowercase — the form a
 * compound carries ("undzwanzig" covers all but nine numbers). Standing
 * alone they take the eyebrow's capital, which the compound rule applies.
 */
const DE_TENS = ["", "", "zwanzig", "dreißig", "vierzig", "fünfzig", "sechzig", "siebzig", "achtzig", "neunzig"];

/**
 * French 1–19, indexed by the number; dix-sept through dix-neuf are table
 * words like the rest, so the compound rule below only joins tens and ones.
 */
const FR_ONES = [
  "", "Un", "Deux", "Trois", "Quatre", "Cinq", "Six", "Sept", "Huit", "Neuf",
  "Dix", "Onze", "Douze", "Treize", "Quatorze", "Quinze", "Seize", "Dix-Sept",
  "Dix-Huit", "Dix-Neuf",
];

/**
 * French tens words up to sixty, indexed by the tens digit. The table stops
 * at sixty on purpose: seventy onward French counts in vingts, and those
 * words belong to the branches below, not to a tens table.
 */
const FR_TENS = ["", "", "Vingt", "Trente", "Quarante", "Cinquante", "Soixante"];

/**
 * The written-out ordinal word for a chapter number in the given locale.
 * Whole numbers in 1–99 come back as words; 0 and everything past 99 come
 * back as digits. Negative and fractional input throws.
 */
export function chapterOrdinal(n: number, locale: NumberLocale): string {
  if (!Number.isInteger(n) || n < 0) {
    throw new RangeError(`a chapter number is a whole number from 0 up, got ${n}`);
  }
  // Outside the written range the digits speak: zero, and the chapters past it.
  if (n === 0 || n > 99) return String(n);
  switch (locale) {
    case "en":
      return english(n);
    case "de":
      return german(n);
    case "fr":
      return french(n);
  }
}

/** One to ninety-nine in English: tens-unit, joined by a hyphen. */
function english(n: number): string {
  if (n < 20) return EN_ONES[n];
  const tens = Math.trunc(n / 10);
  const unit = n % 10;
  const base = EN_TENS[tens];
  return unit === 0 ? base : `${base}-${EN_ONES[unit]}`;
}

/**
 * One to ninety-nine in German: one fused compound word, unit-and-tens.
 * The compound says "ein", never "eins" — Einundzwanzig — while the ones
 * table keeps its full form for the words that stand alone.
 */
function german(n: number): string {
  if (n < 20) return DE_ONES[n];
  const tens = Math.trunc(n / 10);
  const unit = n % 10;
  const tensWord = DE_TENS[tens];
  if (unit === 0) {
    return `${tensWord.charAt(0).toUpperCase()}${tensWord.slice(1)}`;
  }
  const unitWord = unit === 1 ? "Ein" : DE_ONES[unit];
  return `${unitWord}und${tensWord}`;
}

/**
 * One to ninety-nine in French: twenty to sixty-nine are base-and-unit;
 * seventy onward the vingts count — soixante carries the tens of the
 * seventies, quatre-vingt the twenties of the eighties and nineties. The
 * "et" forms stay literary and unhyphenated; the plural s of
 * "Quatre-Vingts" drops once a unit follows.
 */
function french(n: number): string {
  if (n < 20) return FR_ONES[n];
  const tens = Math.trunc(n / 10);
  const unit = n % 10;
  if (tens <= 6) {
    const base = FR_TENS[tens];
    if (unit === 0) return base;
    return unit === 1 ? `${base} et Un` : `${base}-${FR_ONES[unit]}`;
  }
  if (tens === 7) {
    if (unit === 0) return "Soixante-Dix";
    return unit === 1 ? "Soixante et Onze" : `Soixante-${FR_ONES[unit + 10]}`;
  }
  if (tens === 8) {
    if (unit === 0) return "Quatre-Vingts";
    return unit === 1 ? "Quatre-Vingt-Un" : `Quatre-Vingt-${FR_ONES[unit]}`;
  }
  if (unit === 0) return "Quatre-Vingt-Dix";
  return unit === 1 ? "Quatre-Vingt-Onze" : `Quatre-Vingt-${FR_ONES[unit + 10]}`;
}
