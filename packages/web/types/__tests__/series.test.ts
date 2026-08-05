/**
 * Series type tests — type acceptance + RULE-17 parity.
 *
 * Each sample is a fully-populated literal annotated with the interface type.
 * This gives two layers of enforcement (see lib/api/__tests__/types-parity.test.ts):
 *   1. `vitest run`  — `Object.keys(sample)` returns the real runtime keys.
 *   2. `tsc`          — the sample must satisfy the interface, so any missing or
 *      extra REQUIRED field is a compile error on the annotation.
 * snake_case is preserved to mirror the Pydantic SSOT
 * (apps/api/narrare/series/schemas.py).
 */

import { describe, expect, it } from "vitest";
import type {
  BandSummary,
  JoinEntryTreatment,
  JoinPreview,
  JoinResult,
  Series,
  SeriesCreate,
  SeriesSettings,
  SeriesStatus,
  SeriesSummary,
  SeriesUpdate,
} from "../series";

function fieldNames<T extends object>(sample: T): string[] {
  return Object.keys(sample).sort();
}

describe("Series types mirror Pydantic (RULE-17)", () => {
  it("SeriesResponse → Series has all 10 fields", () => {
    const sample: Series = {
      id: "uuid-1",
      user_id: "user-1",
      title: "The Expanse",
      subtitle: null,
      description: null,
      genre: "sci-fi",
      writing_language: "en",
      status: "draft",
      planned_novel_count: 9,
      novel_count: 0,
    };
    expect(fieldNames(sample)).toEqual([
      "description",
      "genre",
      "id",
      "novel_count",
      "planned_novel_count",
      "status",
      "subtitle",
      "title",
      "user_id",
      "writing_language",
    ]);
  });

  it("SeriesSummary → 5 fields", () => {
    const sample: SeriesSummary = {
      id: "uuid-1",
      title: "The Expanse",
      subtitle: null,
      status: "active",
      novel_count: 4,
    };
    expect(fieldNames(sample)).toEqual(["id", "novel_count", "status", "subtitle", "title"]);
  });

  it("SeriesCreate → request body shape", () => {
    const sample: SeriesCreate = {
      title: "The Expanse",
      subtitle: "A space opera",
      description: "...",
      genre: "sci-fi",
      writing_language: "en",
      status: "draft",
      planned_novel_count: 9,
    };
    expect(fieldNames(sample)).toEqual([
      "description",
      "genre",
      "planned_novel_count",
      "status",
      "subtitle",
      "title",
      "writing_language",
    ]);
  });

  it("SeriesUpdate → all-optional patch body", () => {
    const sample: SeriesUpdate = {
      title: "Renamed",
      subtitle: null,
      description: null,
      genre: null,
      writing_language: null,
      status: "active",
      planned_novel_count: null,
    };
    expect(fieldNames(sample)).toEqual([
      "description",
      "genre",
      "planned_novel_count",
      "status",
      "subtitle",
      "title",
      "writing_language",
    ]);
  });

  it("SeriesSettings → 2 fields", () => {
    const sample: SeriesSettings = {
      series_id: "uuid-1",
      author_voice: null,
    };
    expect(fieldNames(sample)).toEqual(["author_voice", "series_id"]);
  });

  it("BandSummary → 5 fields mirroring BandSummaryResponse", () => {
    const sample: BandSummary = {
      novel_id: "novel-1",
      full_summary: "The crew discovers…",
      short_summary: "Discovery.",
      override: null,
      generated_at: "2026-08-02T12:00:00Z",
    };
    expect(fieldNames(sample)).toEqual([
      "full_summary",
      "generated_at",
      "novel_id",
      "override",
      "short_summary",
    ]);
  });

  it("JoinEntryTreatment → 7 fields with scope + reason_code literals", () => {
    const sample: JoinEntryTreatment = {
      entry_id: "entry-1",
      slug: "magic",
      entity_type: "system",
      current_scope: "novel",
      target_scope: "series",
      reason_code: "entity_default_canon",
      reason: "Entity type 'system' defaults to Canon",
    };
    expect(fieldNames(sample)).toEqual([
      "current_scope",
      "entity_type",
      "entry_id",
      "reason",
      "reason_code",
      "slug",
      "target_scope",
    ]);
  });

  it("JoinPreview → 4 fields incl. treatments array", () => {
    const sample: JoinPreview = {
      series_id: "s1",
      novel_id: "n1",
      canon_empty: true,
      treatments: [],
    };
    expect(fieldNames(sample)).toEqual(["canon_empty", "novel_id", "series_id", "treatments"]);
  });

  it("JoinResult → 5 fields", () => {
    const sample: JoinResult = {
      series_id: "s1",
      novel_id: "n1",
      position: 1,
      promoted_to_canon: 2,
      kept_as_overlay: 3,
    };
    expect(fieldNames(sample)).toEqual([
      "kept_as_overlay",
      "novel_id",
      "position",
      "promoted_to_canon",
      "series_id",
    ]);
  });
});

describe("Series literal unions", () => {
  it("SeriesStatus is exactly draft | active | completed", () => {
    const statuses: SeriesStatus[] = ["draft", "active", "completed"];
    expect(statuses).toHaveLength(3);
    // Compile-time: assigning any other literal would fail tsc.
    const draft: SeriesStatus = "draft";
    expect(draft).toBe("draft");
  });
});
