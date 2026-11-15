/**
 * The shelf's search and filter model, pinned without a DOM. The disclosed
 * shapes (Task 7): search is the whole trimmed query, case-insensitive —
 * a substring of the title or of any genre component, and a figure query
 * (a bare or thousands-grouped integer) matches word_count or chapter_count
 * by EQUALITY, never as a substring of the count; a figure still searches
 * title/genre text as text. Genres facet by their comma-joined components,
 * first appearance wins the label's casing, one book counts once per
 * component. Status facets answer only the vocabulary the server validates
 * (draft/revision/final), in that order, only when a loaded row carries the
 * value. Composition: OR within a facet group, AND across groups and the
 * search. The archive toggle is the server's own parameter — the model
 * filters whatever population the list query answered.
 */
import { describe, expect, it } from "vitest";

import type { Novel } from "@shell/lib/api/client";

import {
  filterGrid,
  genreComponents,
  genreFacets,
  hasActiveFilters,
  matchesSearch,
  parseFigure,
  statusFacets,
} from "./shelfFilter";

/** A novel row with the fields the model reads; the rest ride defaults. */
function row(id: string, extra: Partial<Novel> = {}): Novel {
  return {
    id,
    title: `Buch ${id}`,
    genre: null,
    blurb: null,
    author: null,
    language: null,
    chapter_count: 0,
    word_count: 0,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-10T10:00:00Z",
    last_exported_at: null,
    status: null,
    series_title: null,
    series_volume: null,
    archived_at: null,
    target_words: null,
    ...extra,
  };
}

describe("genreComponents — the joined genre splits into its parts", () => {
  it("splits a comma-joined genre and trims each component", () => {
    expect(genreComponents("Science Fiction, Mystery")).toEqual(["Science Fiction", "Mystery"]);
    expect(genreComponents(" Mystery ,Historisch ")).toEqual(["Mystery", "Historisch"]);
  });

  it("answers nothing for a null, empty or separator-only genre", () => {
    expect(genreComponents(null)).toEqual([]);
    expect(genreComponents(undefined)).toEqual([]);
    expect(genreComponents("")).toEqual([]);
    expect(genreComponents(" , ")).toEqual([]);
  });

  it("keeps a single genre as its one component", () => {
    expect(genreComponents("Mystery")).toEqual(["Mystery"]);
  });
});

describe("genreFacets — derived from the loaded rows' real genres", () => {
  it("counts each component once per book, in first-appearance order", () => {
    const rows = [
      row("a", { genre: "Science Fiction, Mystery" }),
      row("b", { genre: "Mystery" }),
      row("c", { genre: "Literary" }),
      row("d", { genre: null }),
    ];
    expect(genreFacets(rows)).toEqual([
      { label: "Science Fiction", count: 1 },
      { label: "Mystery", count: 2 },
      { label: "Literary", count: 1 },
    ]);
  });

  it("merges case variants under the first-seen label", () => {
    const rows = [row("a", { genre: "Mystery" }), row("b", { genre: "mystery" })];
    expect(genreFacets(rows)).toEqual([{ label: "Mystery", count: 2 }]);
  });

  it("counts a repeated component within one book only once", () => {
    expect(genreFacets([row("a", { genre: "Mystery, Mystery" })])).toEqual([
      { label: "Mystery", count: 1 },
    ]);
  });

  it("answers no facets for a shelf without genres", () => {
    expect(genreFacets([row("a"), row("b", { genre: " " })])).toEqual([]);
    expect(genreFacets([])).toEqual([]);
  });
});

describe("statusFacets — the vocabulary the rows actually carry", () => {
  it("answers draft, revision, final in vocabulary order, with real counts", () => {
    const rows = [
      row("a", { status: "final" }),
      row("b", { status: "draft" }),
      row("c", { status: "draft" }),
      row("d", { status: "revision" }),
      row("e", { status: null }),
    ];
    expect(statusFacets(rows)).toEqual([
      { value: "draft", count: 2 },
      { value: "revision", count: 1 },
      { value: "final", count: 1 },
    ]);
  });

  it("omits a value no row carries, and unknown values entirely", () => {
    expect(statusFacets([row("a", { status: "revision" })])).toEqual([
      { value: "revision", count: 1 },
    ]);
    // The server validates the vocabulary; an unknown value is no facet
    // (the card draws no pill for it either).
    expect(statusFacets([row("a", { status: "planung" })])).toEqual([]);
    expect(statusFacets([row("a")])).toEqual([]);
  });
});

describe("parseFigure — a number is a whole count, grouped as the locale prints it", () => {
  it("reads a bare integer", () => {
    expect(parseFigure("24150")).toBe(24150);
    expect(parseFigure("0")).toBe(0);
    expect(parseFigure(" 12 ")).toBe(12);
  });

  it("reads the thousands-grouped forms the three locales print", () => {
    expect(parseFigure("24.150")).toBe(24150); // de-DE
    expect(parseFigure("24,150")).toBe(24150); // en
    expect(parseFigure("24 150")).toBe(24150); // fr
    expect(parseFigure("24\u00a0150")).toBe(24150); // fr NBSP
    expect(parseFigure("24\u202f150")).toBe(24150); // fr narrow NBSP
    expect(parseFigure("1.234.567")).toBe(1234567);
  });

  it("refuses decimals, signs and mixed text — counts are whole and unsigned", () => {
    expect(parseFigure("3.5")).toBeNull();
    expect(parseFigure("3,5")).toBeNull();
    expect(parseFigure("-12")).toBeNull();
    expect(parseFigure("12abc")).toBeNull();
    expect(parseFigure("12 34")).toBeNull(); // not a thousands group
    expect(parseFigure("")).toBeNull();
    expect(parseFigure("salt")).toBeNull();
  });
});

describe("matchesSearch — titles, genres and figures, the disclosed shape", () => {
  const novel = row("a", {
    title: "The Salt Road",
    genre: "Literary, Historisch",
    word_count: 24150,
    chapter_count: 12,
  });

  it("an empty or whitespace query matches every book", () => {
    expect(matchesSearch(novel, "")).toBe(true);
    expect(matchesSearch(novel, "   ")).toBe(true);
  });

  it("matches the title case-insensitively, as a substring", () => {
    expect(matchesSearch(novel, "salt")).toBe(true);
    expect(matchesSearch(novel, "SALT ROAD")).toBe(true);
    expect(matchesSearch(novel, "road")).toBe(true);
    expect(matchesSearch(novel, "winter")).toBe(false);
  });

  it("matches any genre component, not only the first", () => {
    expect(matchesSearch(novel, "historisch")).toBe(true);
    expect(matchesSearch(novel, "liter")).toBe(true);
    expect(matchesSearch(novel, "mystery")).toBe(false);
  });

  it("a figure matches word_count or chapter_count by equality", () => {
    expect(matchesSearch(novel, "24150")).toBe(true);
    expect(matchesSearch(novel, "24.150")).toBe(true);
    expect(matchesSearch(novel, "12")).toBe(true);
    expect(matchesSearch(row("b", { chapter_count: 24150 }), "24150")).toBe(true);
  });

  it("a figure never matches as a substring of a count", () => {
    expect(matchesSearch(novel, "2415")).toBe(false);
    expect(matchesSearch(novel, "415")).toBe(false);
    expect(matchesSearch(novel, "2")).toBe(false);
  });

  it("a figure still searches title and genre text as text", () => {
    const numbered = row("b", { title: "Station 7", word_count: 90000, chapter_count: 3 });
    expect(matchesSearch(numbered, "7")).toBe(true);
    expect(matchesSearch(numbered, "90000")).toBe(true);
  });

  it("a decimal query is text, never a rounded count", () => {
    expect(matchesSearch(novel, "3.5")).toBe(false);
    expect(matchesSearch(row("b", { title: "3.5" }), "3.5")).toBe(true);
  });
});

describe("filterGrid — search × facets compose, OR within, AND across", () => {
  const rows = [
    row("hero", { title: "Dead Signal", genre: "Science Fiction", status: "draft", word_count: 48342 }),
    row("winter", { title: "Winterhaus", genre: "Mystery", status: null }),
    row("salt", { title: "The Salt Road", genre: "Literary", status: "revision", word_count: 24150 }),
    row("arkona", { title: "Der Nebel von Arkona", genre: "Historisch", status: "final" }),
    row("both", { title: "Grenzgänger", genre: "Mystery, Historisch", status: "draft" }),
  ];

  it("no filters keep the whole population in order", () => {
    expect(filterGrid(rows, { query: "", genres: [], statuses: [] })).toEqual(rows);
  });

  it("one genre facet keeps its books; two genres OR", () => {
    expect(filterGrid(rows, { query: "", genres: ["Mystery"], statuses: [] }).map((n) => n.id)).toEqual([
      "winter",
      "both",
    ]);
    expect(
      filterGrid(rows, { query: "", genres: ["Mystery", "Historisch"], statuses: [] }).map((n) => n.id),
    ).toEqual(["winter", "arkona", "both"]);
  });

  it("genre matching is case-insensitive against the components", () => {
    expect(filterGrid(rows, { query: "", genres: ["mystery"], statuses: [] }).map((n) => n.id)).toEqual([
      "winter",
      "both",
    ]);
  });

  it("a status facet keeps only its value; a null status matches none", () => {
    expect(filterGrid(rows, { query: "", genres: [], statuses: ["draft"] }).map((n) => n.id)).toEqual([
      "hero",
      "both",
    ]);
    expect(filterGrid(rows, { query: "", genres: [], statuses: ["revision", "final"] }).map((n) => n.id)).toEqual([
      "salt",
      "arkona",
    ]);
  });

  it("search and facets AND across their groups", () => {
    expect(
      filterGrid(rows, { query: "nebel", genres: ["Historisch"], statuses: ["final"] }).map((n) => n.id),
    ).toEqual(["arkona"]);
    // The search alone would match, the facet excludes it.
    expect(filterGrid(rows, { query: "nebel", genres: ["Mystery"], statuses: [] })).toEqual([]);
    // The facet alone would match, the search excludes it.
    expect(filterGrid(rows, { query: "salt", genres: [], statuses: ["draft"] })).toEqual([]);
  });

  it("a figure search composes with facets the same way", () => {
    expect(filterGrid(rows, { query: "24150", genres: ["Literary"], statuses: [] }).map((n) => n.id)).toEqual([
      "salt",
    ]);
    expect(filterGrid(rows, { query: "24150", genres: ["Mystery"], statuses: [] })).toEqual([]);
  });
});

describe("hasActiveFilters — what the empty-results state and the clear answer", () => {
  it("is false for the untouched state, whitespace included", () => {
    expect(hasActiveFilters({ query: "", genres: [], statuses: [] })).toBe(false);
    expect(hasActiveFilters({ query: "   ", genres: [], statuses: [] })).toBe(false);
  });

  it("is true for a query, a genre or a status", () => {
    expect(hasActiveFilters({ query: "salt", genres: [], statuses: [] })).toBe(true);
    expect(hasActiveFilters({ query: "", genres: ["Mystery"], statuses: [] })).toBe(true);
    expect(hasActiveFilters({ query: "", genres: [], statuses: ["draft"] })).toBe(true);
  });
});
