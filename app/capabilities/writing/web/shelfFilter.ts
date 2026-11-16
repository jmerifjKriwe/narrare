/**
 * The shelf's search and filter model (Task 7) — client-side over the list
 * the novels query answered, single user, no request per keystroke. The
 * disclosed shapes, pinned by shelfFilter.test.ts:
 *
 * - Search is the whole trimmed query, case-insensitive: a substring of the
 *   title or of any genre component. A figure query — a bare integer or a
 *   thousands-grouped one (de `.`, en `,`, fr space/NBSP/narrow NBSP) —
 *   matches `word_count` or `chapter_count` by EQUALITY, never as a
 *   substring of the count; it still searches title/genre text as text, so
 *   a book called „Station 7" answers „7" too. Decimals and signs are text,
 *   never rounded counts — the counts are whole and unsigned.
 * - Genres are one comma-joined string (the new-book dialog's multi-select
 *   joins with ", "); the facets split it into its components, trim them,
 *   and merge case variants under the first-seen label. One book counts
 *   once per component, and the facet order is first appearance across the
 *   loaded rows — deterministic, never a reshuffle.
 * - Status facets answer only the vocabulary the server validates
 *   (draft/revision/final), in that order, only for values a loaded row
 *   carries; a null status is no answer and matches no status facet.
 * - Composition: OR within a facet group, AND across the groups and the
 *   search. The archive toggle is the server's own `include_archived`
 *   parameter (a real refetch, see useNovelsQuery) — this model filters
 *   whatever population that answer carried, archived rows included.
 *
 * No React, no i18n, no requests — the rules the page renders, testable on
 * their own. Facet counts cover the whole loaded population (the hero
 * included); the grid itself never doubles the hero (shelf.ts's rule).
 */

import type { Novel } from "@shell/lib/api/client";

/** One genre facet: the component's first-seen label and its book count. */
export type GenreFacet = { label: string; count: number };

/** One status facet: the vocabulary value and its book count. */
export type StatusFacet = { value: string; count: number };

/** The status vocabulary's order — the server validates these values, and
 *  the facets answer them in the same order the pills wear them. */
const STATUS_ORDER = ["draft", "revision", "final"] as const;

/** The joined genre's components: split on the comma the dialog joins
 *  with, trimmed, empties dropped. Null or blank is no genre at all. */
export function genreComponents(genre: string | null | undefined): string[] {
  if (genre == null) return [];
  return genre
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part !== "");
}

/** The genre facets of the loaded rows, first appearance first. Case
 *  variants merge under the first-seen label; a book counts once per
 *  component even when it repeats the component in its own join. */
export function genreFacets(novels: readonly Novel[]): GenreFacet[] {
  const facets = new Map<string, GenreFacet>();
  for (const novel of novels) {
    const counted = new Set<string>();
    for (const component of genreComponents(novel.genre)) {
      const key = component.toLowerCase();
      if (counted.has(key)) continue;
      counted.add(key);
      const facet = facets.get(key);
      if (facet !== undefined) facet.count += 1;
      else facets.set(key, { label: component, count: 1 });
    }
  }
  return [...facets.values()];
}

/** The status facets of the loaded rows: vocabulary order, only the values
 *  the rows actually carry. An unknown value is no facet — the card draws
 *  no pill for it either, and the facet never guesses a label. */
export function statusFacets(novels: readonly Novel[]): StatusFacet[] {
  const counts = new Map<string, number>();
  for (const novel of novels) {
    if (novel.status == null) continue;
    counts.set(novel.status, (counts.get(novel.status) ?? 0) + 1);
  }
  return STATUS_ORDER.filter((value) => counts.has(value)).map((value) => ({
    value,
    count: counts.get(value) ?? 0,
  }));
}

/** A bare integer, or a thousands-grouped one: 1–3 leading digits then
 *  groups of exactly three, separated by the mark the locale prints
 *  (de `.`, en `,`, fr space, NBSP, narrow NBSP). */
const FIGURE_PLAIN = /^\d+$/;
const FIGURE_GROUPED = /^\d{1,3}(?:[.,\u00a0\u202f ]\d{3})+$/;
const FIGURE_MARKS = /[.,\u00a0\u202f ]/g;

/** The query as a whole count, or null when it is not one. Decimals,
 *  signs and mixed text are text — a count is whole and unsigned, and
 *  „3.5" is no rounded 3 or 35. Beyond the safe integer range the figure
 *  is no figure either: the comparison could not be honest. */
export function parseFigure(query: string): number | null {
  const trimmed = query.trim();
  let digits: string;
  if (FIGURE_PLAIN.test(trimmed)) digits = trimmed;
  else if (FIGURE_GROUPED.test(trimmed)) digits = trimmed.replace(FIGURE_MARKS, "");
  else return null;
  const value = Number(digits);
  return Number.isSafeInteger(value) ? value : null;
}

/** Does the book answer the search? The whole trimmed query,
 *  case-insensitive: a figure matches a count by equality (and still
 *  searches the text as text); anything else is a substring of the title
 *  or of any genre component. An empty query answers every book. */
export function matchesSearch(novel: Novel, query: string): boolean {
  const trimmed = query.trim();
  if (trimmed === "") return true;
  const figure = parseFigure(trimmed);
  if (figure !== null && (novel.word_count === figure || novel.chapter_count === figure)) {
    return true;
  }
  const needle = trimmed.toLowerCase();
  if (novel.title.toLowerCase().includes(needle)) return true;
  return genreComponents(novel.genre).some((component) => component.toLowerCase().includes(needle));
}

/** The client-side filter state — transient, in the page's own memory.
 *  The archive toggle is not here: it is the list query's parameter. */
export type ShelfFilterState = {
  query: string;
  genres: readonly string[];
  statuses: readonly string[];
};

/** The facet half of the composition: OR within each group, AND across
 *  the groups. Genre labels compare case-insensitively against the book's
 *  components; a null status answers no status facet. */
function matchesFacets(novel: Novel, genres: readonly string[], statuses: readonly string[]): boolean {
  if (genres.length > 0) {
    const components = genreComponents(novel.genre).map((component) => component.toLowerCase());
    if (!genres.some((label) => components.includes(label.toLowerCase()))) return false;
  }
  if (statuses.length > 0) {
    if (novel.status == null || !statuses.includes(novel.status)) return false;
  }
  return true;
}

/** The grid under the composed filters: search × genres × statuses, the
 *  population's own order kept (the shelf's newest-first rule upstream). */
export function filterGrid(novels: readonly Novel[], state: ShelfFilterState): Novel[] {
  return novels.filter(
    (novel) => matchesSearch(novel, state.query) && matchesFacets(novel, state.genres, state.statuses),
  );
}

/** Is the shelf narrowed at all? The empty-results panel answers only a
 *  real narrowing — an untouched grid may legitimately stand empty (the
 *  hero alone on the shelf), and that is no failed search. */
export function hasActiveFilters(state: ShelfFilterState): boolean {
  return state.query.trim() !== "" || state.genres.length > 0 || state.statuses.length > 0;
}
