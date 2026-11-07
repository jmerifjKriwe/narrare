/**
 * The client half of the one word rule (R31). The server is the authority:
 * `repository.py` counts with a single whitespace class — the database's
 * `\s`, plus the three near spaces a browser counts (U+00A0, U+2007, U+202F)
 * — and trims and splits with that one class so the two ends cannot drift.
 * This file repeats exactly that class in JavaScript, and JavaScript's own
 * `\s` is wider than the server's in exactly one member: U+FEFF, which is a
 * character, not a gap. The explicit code-point list below is JS `\s` minus
 * U+FEFF, so a zero-width no-break space joins words the way the server
 * says it does. The two implementations move together.
 */

/**
 * The shared class: trim the ends with it, split the middle with it, judge
 * emptiness by the trimmed value — never three sets, one.
 */
const WORD_GAP = /[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/;
const WORD_EDGE = new RegExp(`^${WORD_GAP.source}|${WORD_GAP.source}$`, "g");

/**
 * Count the words of a chapter body — the Markdown the storage format keeps,
 * the same string the server counts. A body that is empty or whitespace-only
 * by the class is worth zero, which a bare split would count as its one
 * empty token.
 */
export function countWords(markdown: string): number {
  const trimmed = markdown.replace(WORD_EDGE, "");
  return trimmed === "" ? 0 : trimmed.split(WORD_GAP).length;
}

import { formatNumber } from "./format";

/**
 * The count as the locale groups it — exactly the number the ICU `#` in
 * `chapters.wordCount` prints (both go through the active formatting locale),
 * alone, for the places that show the figure without the word.
 */
export function formatWordCount(count: number): string {
  return formatNumber(count);
}
