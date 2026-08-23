/**
 * Notes type tests — type acceptance + RULE-17 parity.
 *
 * Each sample is a fully-populated literal annotated with the interface type
 * (pattern: types/__tests__/series.test.ts):
 *   1. `vitest run` — `Object.keys(sample)` returns the real runtime keys.
 *   2. `tsc`        — the sample must satisfy the interface, so any missing or
 *      extra REQUIRED field is a compile error on the annotation.
 * snake_case is preserved to mirror the Pydantic SSOT
 * (apps/api/narrare/notes/schemas.py).
 *
 * Also covers `noteDisplayTitle` (spec §4: empty title → first content line)
 * and `NOTE_TYPE_KEYS`.
 */

import { describe, expect, it } from "vitest";
import {
  NOTE_TYPE_KEYS,
  type Note,
  type NoteCreate,
  type NoteListParams,
  type NoteSearchHit,
  type NoteSearchRequest,
  type NoteSearchResponse,
  type NoteTagsResponse,
  type NoteTypeKey,
  type NoteUpdate,
  noteDisplayTitle,
} from "../notes";

function fieldNames<T extends object>(sample: T): string[] {
  return Object.keys(sample).sort();
}

describe("Notes types mirror Pydantic (RULE-17)", () => {
  it("NoteResponse → Note has all 9 fields", () => {
    const sample: Note = {
      id: "note-1",
      title: "Lighthouse motif",
      content: "The lighthouse appears in every chapter finale.",
      note_type: "idea",
      tags: ["motif", "symbolism"],
      novel_id: null,
      series_id: null,
      created_at: "2026-08-20T10:00:00Z",
      updated_at: "2026-08-21T12:00:00Z",
    };
    expect(fieldNames(sample)).toEqual([
      "content",
      "created_at",
      "id",
      "note_type",
      "novel_id",
      "series_id",
      "tags",
      "title",
      "updated_at",
    ]);
  });

  it("NoteCreate → request body shape (6 fields)", () => {
    const sample: NoteCreate = {
      title: "Quick idea",
      content: "What if the narrator is the lighthouse?",
      note_type: "question",
      tags: ["narrator"],
      novel_id: null,
      series_id: null,
    };
    expect(fieldNames(sample)).toEqual([
      "content",
      "note_type",
      "novel_id",
      "series_id",
      "tags",
      "title",
    ]);
  });

  it("NoteUpdate → all-optional patch body (single field is valid)", () => {
    const sample: NoteUpdate = { title: null };
    expect(fieldNames(sample)).toEqual(["title"]);
    // Explicit null clears a field (schemas.py NoteUpdateRequest semantics).
    expect(sample.title).toBeNull();
  });

  it("NoteListParams → all-optional (empty object valid)", () => {
    const empty: NoteListParams = {};
    expect(fieldNames(empty)).toEqual([]);
    const full: NoteListParams = {
      note_type: "concept",
      tag: "motif",
      novel_id: "novel-1",
      series_id: "series-1",
      q: "lighthouse",
      limit: 25,
      offset: 50,
    };
    expect(fieldNames(full)).toEqual([
      "limit",
      "note_type",
      "novel_id",
      "offset",
      "q",
      "series_id",
      "tag",
    ]);
  });

  it("NoteTagsResponse → single tags field", () => {
    const sample: NoteTagsResponse = { tags: ["motif", "symbolism"] };
    expect(fieldNames(sample)).toEqual(["tags"]);
  });

  it("NoteSearchHit → Note + similarity (10 fields)", () => {
    const sample: NoteSearchHit = {
      id: "note-1",
      title: null,
      content: "The lighthouse appears…",
      note_type: "idea",
      tags: [],
      novel_id: null,
      series_id: null,
      created_at: "2026-08-20T10:00:00Z",
      updated_at: "2026-08-20T10:00:00Z",
      // null in lexical mode (schemas.py NoteSearchHit)
      similarity: null,
    };
    expect(fieldNames(sample)).toEqual([
      "content",
      "created_at",
      "id",
      "note_type",
      "novel_id",
      "series_id",
      "similarity",
      "tags",
      "title",
      "updated_at",
    ]);
    const semantic: NoteSearchHit = { ...sample, similarity: 0.87 };
    expect(semantic.similarity).toBe(0.87);
  });

  it("NoteSearchRequest → 6 fields, query required", () => {
    const sample: NoteSearchRequest = {
      query: "who tends the light",
      note_type: "question",
      tag: "lighthouse",
      novel_id: "novel-1",
      // Optional-only on the client (no explicit-null clearing in search
      // filters — unlike NoteUpdate, where null clears a stored field).
      series_id: "series-1",
      limit: 10,
    };
    expect(fieldNames(sample)).toEqual([
      "limit",
      "note_type",
      "novel_id",
      "query",
      "series_id",
      "tag",
    ]);
  });

  it("NoteSearchResponse → 3 fields with mode badge", () => {
    const sample: NoteSearchResponse = {
      mode: "semantic",
      query: "who tends the light",
      results: [],
    };
    expect(fieldNames(sample)).toEqual(["mode", "query", "results"]);
    const lexical: NoteSearchResponse = { ...sample, mode: "lexical" };
    expect(lexical.mode).toBe("lexical");
  });
});

describe("NoteTypeKey literal union", () => {
  it("is exactly idea | concept | question | other", () => {
    const keys: NoteTypeKey[] = ["idea", "concept", "question", "other"];
    expect(keys).toHaveLength(4);
    // Compile-time: assigning any other literal would fail tsc.
    const idea: NoteTypeKey = "idea";
    expect(idea).toBe("idea");
  });

  it("NOTE_TYPE_KEYS lists all keys in domain order", () => {
    expect(NOTE_TYPE_KEYS).toEqual(["idea", "concept", "question", "other"]);
  });
});

describe("noteDisplayTitle (spec §4: empty title → first content line)", () => {
  it("returns the stored title when non-empty", () => {
    expect(noteDisplayTitle({ title: "Lighthouse motif", content: "body" })).toBe(
      "Lighthouse motif",
    );
  });

  it("falls back to the first non-empty content line when title is null", () => {
    expect(
      noteDisplayTitle({
        title: null,
        content: "\n\n  The keeper never sleeps.  \nSecond line.",
      }),
    ).toBe("The keeper never sleeps.");
  });

  it("treats a whitespace-only title as empty", () => {
    expect(noteDisplayTitle({ title: "   ", content: "First line." })).toBe("First line.");
  });

  it("returns empty string for empty or whitespace-only content", () => {
    expect(noteDisplayTitle({ title: null, content: "" })).toBe("");
    expect(noteDisplayTitle({ title: "  ", content: "\n \n\t" })).toBe("");
  });

  it("truncates a long first line to 200 characters", () => {
    const longLine = "x".repeat(350);
    expect(noteDisplayTitle({ title: null, content: longLine })).toHaveLength(200);
  });
});
