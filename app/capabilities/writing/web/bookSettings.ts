import { formatNumber } from "@shell/lib/format";

import { GENRE_PILLS, joinGenres, TARGET_WORDS_MAX } from "./newBook";

/**
 * The book-settings dialog's pure model (W4 Task 19) — the parsing and
 * joining the form rides, beside the new-book dialog's own model
 * (newBook.ts): the word-goal fields accept the locale's thousands
 * separators and answer to the column's shared bounds, the genre pills
 * round-trip the one joined string without losing a free-text part, and
 * the series select resolves the book's link against the user's list.
 *
 * Pure: no React, no state, no server writes. The dialog holds its
 * answers in component state — the dirty rule compares them against the
 * stored baseline, and Speichern carries the diff alone.
 */

/** A word-goal field's answer: a number within the column's bounds, the
 *  honest unset (null — the empty input), or the refusal ("invalid"). */
export type WordGoalAnswer = number | null | "invalid";

/** Parse a word-goal input: empty is the honest unset; the locale's
 *  thousands separators (de „65.000", en „65,000", fr „65 000") are
 *  stripped before the digits answer; anything else — or a value outside
 *  1…2³¹−1, the kernel contract's shared bounds — is the refusal. */
export function parseWordGoal(raw: string): WordGoalAnswer {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  const digits = trimmed.replace(/[.,\u00a0\u202f ]/g, "");
  if (!/^\d+$/.test(digits)) return "invalid";
  const value = Number(digits);
  if (!Number.isSafeInteger(value) || value < 1 || value > TARGET_WORDS_MAX) return "invalid";
  return value;
}

/** A stored goal as the input opens on it: the locale's grouped figure
 *  (the draft's „65.000" face), the unset as the empty field. */
export function formatGoalInput(value: number | null): string {
  return value === null ? "" : formatNumber(value);
}

/** The genre string as the pills open on it: the known vocabulary's
 *  values in the string's own order, and the remainder — a free-text part
 *  no pill names — kept verbatim so a save never silently drops it. */
export function genresFromNovel(genre: string | null): { pills: string[]; rest: string } {
  const parts = (genre ?? "")
    .split(", ")
    .map((part) => part.trim())
    .filter((part) => part !== "");
  const pills = parts.filter((part) => GENRE_PILLS.includes(part));
  const rest = parts.filter((part) => !GENRE_PILLS.includes(part)).join(", ");
  return { pills, rest };
}

/** The one string the PATCH carries: the selected pills joined the
 *  canonical way, the remainder appended — none of either is the honest
 *  null (the cleared genre). */
export function joinGenresWithRest(pills: readonly string[], rest: string): string | null {
  const known = joinGenres(pills);
  const trimmedRest = rest.trim();
  const joined = [known, trimmedRest].filter((part) => part !== "").join(", ");
  return joined === "" ? null : joined;
}

/** The book's series link as the select's value: the list row whose title
 *  the novel carries (NovelRead joins the title, not the id). A link whose
 *  series is gone — or no link at all — is the standalone option (null). */
export function seriesIdForTitle(
  series: readonly { id: string; title: string }[],
  seriesTitle: string | null,
): string | null {
  if (seriesTitle === null) return null;
  return series.find((row) => row.title === seriesTitle)?.id ?? null;
}

/** A volume input's answer: empty is the honest unset, a whole number
 *  from one the volume, anything else the refusal. The series link's
 *  presence is the form's own cross-field rule (the server checks it too). */
export function parseVolume(raw: string): WordGoalAnswer {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  if (!/^\d+$/.test(trimmed)) return "invalid";
  const value = Number(trimmed);
  if (!Number.isSafeInteger(value) || value < 1) return "invalid";
  return value;
}
