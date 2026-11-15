import type { MessageKey } from "@shell/lib/i18n";

/**
 * The new-book dialog's pure model — the wizard step 1 seam shapes the
 * dialog re-owns on this side of the capability boundary (rule 1: a
 * capability never imports another, and no shared shell helper carries
 * these yet). The five genre pills join to the one ≤80-char string the
 * backend's `genre` column binds; a pill whose addition would overflow is
 * disabled with the honest note instead of silently dropping the choice.
 * The word target keeps the draft's default and the Integer column's own
 * ceiling, and the format bands are the draft gauge's boundaries — the
 * same bands the wizard's step 1 draws, so a target reads identically on
 * both surfaces.
 *
 * Pure: no React, no state, no server writes. The dialog holds its answers
 * in component state — transient by design, the draft carries no
 * draft-persistence, and an unmounted dialog is a forgotten one.
 */

/**
 * The five genre pills, in the draft's order. The `value` is the canonical
 * label the backend receives and the cover system recognizes (cover.ts's
 * CHANNEL_ALIASES carries exactly these five); the visible face is
 * localized through the catalog key, so the joined string a reader sends
 * never depends on the language they read the UI in.
 */
export const GENRE_PILL_DEFS: readonly { value: string; key: MessageKey }[] = [
  { value: "Science Fiction & Speculative", key: "writing.shelf.dialog.genre.scifi" },
  { value: "Mystery & Noir", key: "writing.shelf.dialog.genre.mystery" },
  { value: "Historischer Roman", key: "writing.shelf.dialog.genre.historical" },
  { value: "Literarische Belletristik", key: "writing.shelf.dialog.genre.literary" },
  { value: "Low Fantasy / Magischer Realismus", key: "writing.shelf.dialog.genre.lowfantasy" },
];

export const GENRE_PILLS: readonly string[] = GENRE_PILL_DEFS.map((pill) => pill.value);

/** The backend's `genre` ceiling (writing/schemas.py): the joined string's cap. */
export const GENRE_CAP = 80;

/** The draft's default target and the Integer column's own ceiling — the
 *  same bounds NovelCreate and SetupRequest carry. */
export const DEFAULT_TARGET_WORDS = 65_000;
export const TARGET_WORDS_MAX = 2_147_483_647;

/** The Normseite's word count the draft's „240 Normseiten" at 65.000 implies. */
export const WORDS_PER_NORMSEITE = 270;

/** The one string the backend receives: the selected pills, joined ", ". */
export function joinGenres(pills: readonly string[]): string {
  return pills.join(", ");
}

/** Whether adding `pill` to the selection would overflow the 80-char cap. A
 *  pill already selected is never an "add" — removing it is always allowed. */
export function wouldOverflow(pills: readonly string[], pill: string): boolean {
  if (pills.includes(pill)) return false;
  return joinGenres([...pills, pill]).length > GENRE_CAP;
}

/** The gauge's four format categories, in the draft's order — the wizard
 *  step 1's own boundaries, so both surfaces band a target identically. */
export type Band = "short" | "novella" | "novel" | "epic";
export const BAND_ORDER: readonly Band[] = ["short", "novella", "novel", "epic"];

/** The band a word target falls in — the draft's gauge boundaries. */
export function wordBand(words: number): Band {
  if (words < 10_000) return "short";
  if (words < 50_000) return "novella";
  if (words < 100_000) return "novel";
  return "epic";
}
