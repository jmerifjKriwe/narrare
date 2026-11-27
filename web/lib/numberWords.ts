/**
 * The locale number-words util (W4 Task 11): the workspace's scene header
 * writes its chapter and scene ordinals out — „Kapitel Eins · Szene Zwei" —
 * in the active language's catalog (design §6.3). The cardinals are the
 * drafted voice: the noun carries the case, the word stays the plain
 * cardinal („Szene Zwei", not „Zweite Szene").
 *
 * The words live in the catalogs, so a language writes them where it writes
 * everything else. There is no per-language list here and no `locale`
 * parameter: the active language is the only one whose catalog is loaded.
 *
 * The bound is twenty. Beyond it — and for every value that is not a
 * positive integer — the digit stands: a manuscript with a hundred chapters
 * reads „Kapitel 100", never a guessed word. The fallback is the honest
 * neutral, not an error: the header always names its ordinal.
 */
import { t, type MessageKey } from "./i18n";

/** The last number the util writes out; the first digit fallback is 21. */
export const NUMBER_WORD_BOUND = 20;

/** One catalog key per written number, in cardinal order. */
const WORD_KEYS = [
  "numberWords.01", "numberWords.02", "numberWords.03", "numberWords.04", "numberWords.05",
  "numberWords.06", "numberWords.07", "numberWords.08", "numberWords.09", "numberWords.10",
  "numberWords.11", "numberWords.12", "numberWords.13", "numberWords.14", "numberWords.15",
  "numberWords.16", "numberWords.17", "numberWords.18", "numberWords.19", "numberWords.20",
] as const satisfies readonly MessageKey[];

/** The number as its language's written word, or the digit when the bound or
 *  the integer rule refuses. Lowercase on purpose: the call site capitalizes
 *  where its grammar asks (the German eyebrow's „Kapitel Eins"). */
export function numberWord(value: number): string {
  if (!Number.isInteger(value) || value < 1 || value > NUMBER_WORD_BOUND) {
    return String(value);
  }
  return t(WORD_KEYS[value - 1]);
}

/** The word with its first letter capitalized — the eyebrow's own case. */
export function capitalizedWord(value: number): string {
  const word = numberWord(value);
  return word.charAt(0).toUpperCase() + word.slice(1);
}
