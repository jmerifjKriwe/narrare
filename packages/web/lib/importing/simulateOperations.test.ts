/**
 * Golden-pinned mirror tests (F1, ADR-091 Amendment 2).
 *
 * simulateOperations MUST reproduce the same titles/word counts/order that
 * Core `operations.py` materializes — pinned by the SAME fixture pytest
 * consumes (tests/unit/core/importing/test_operations.py reads
 * packages/web/lib/importing/__fixtures__/operations-golden.json too).
 * The fixture is the SSOT: if a number here contradicts the JSON, the JSON
 * wins. The server stays the authority: commit re-derives candidates and
 * re-validates every op; FE word counts are advisory.
 */

import type { ImportPreviewItem, ImportSelection } from "@/types";
import golden from "./__fixtures__/operations-golden.json";
import { buildAdjustments, serverSupportsOps, simulateOperations } from "./simulateOperations";

type GoldenCase = {
  name: string;
  items: ImportPreviewItem[];
  ops: { splits: Array<{ index: number; at: number[] }>; merges: Array<{ indices: number[] }> };
  expected: Array<{ title: string; word_count: number }>;
};

describe("simulateOperations (golden parity with Core)", () => {
  for (const raw of (golden as { cases: GoldenCase[] }).cases) {
    it(`case: ${raw.name}`, () => {
      const items = raw.items;
      const ops = {
        splits: Object.fromEntries(raw.ops.splits.map((s) => [s.index, [...s.at]])),
        merges: raw.ops.merges.map((m) => [...m.indices]),
      };
      const rows = simulateOperations(items, ops);
      expect(rows.map((r) => ({ title: r.title, word_count: r.wordCount }))).toEqual(
        raw.expected.map(({ title, word_count }) => ({ title, word_count })),
      );
      // Final space is dense: rows are numbered 0..n-1 in materialization order.
      expect(rows.map((r) => r.finalIndex)).toEqual(rows.map((_, i) => i));
    });
  }
});

describe("row keys and merge flags", () => {
  const ITEMS: ImportPreviewItem[] = [
    {
      index: 0,
      suggested_title: "Long",
      word_count: 11,
      source_file: "long.md",
      split_candidates: [
        { ordinal: 0, heading: "Scene A", words_before: 2 },
        { ordinal: 1, heading: "Scene B", words_before: 6 },
      ],
    },
    {
      index: 1,
      suggested_title: "After",
      word_count: 2,
      source_file: "next.md",
      split_candidates: [],
    },
  ];

  it("keys split rows as {origIndex}#{part} and unsplit rows as {origIndex}#0", () => {
    const rows = simulateOperations(ITEMS, { splits: { 0: [0, 1] }, merges: [] });
    expect(rows.map((r) => r.key)).toEqual(["0#0", "0#1", "0#2", "1#0"]);
    expect(rows.map((r) => r.part)).toEqual([0, 1, 2, 0]);
  });

  it("keys merged rows by the run's first original index", () => {
    const rows = simulateOperations(ITEMS, { splits: {}, merges: [[0, 1]] });
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ key: "0#0", isMerged: true, mergedCount: 2, wordCount: 13 });
  });

  it("canonicalizes unsorted merge runs (Core sorts before validating)", () => {
    // Contract note: FE may submit unsorted merge indices — Core canonicalizes.
    const rows = simulateOperations(ITEMS, { splits: {}, merges: [[1, 0]] });
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ key: "0#0", isMerged: true, mergedCount: 2, wordCount: 13 });
  });
});

describe("validateOps mirrors Core validation", () => {
  const ITEMS: ImportPreviewItem[] = [
    {
      index: 0,
      suggested_title: "Long",
      word_count: 11,
      source_file: "long.md",
      split_candidates: [
        { ordinal: 0, heading: "Scene A", words_before: 2 },
        { ordinal: 1, heading: "Scene B", words_before: 6 },
      ],
    },
    {
      index: 1,
      suggested_title: "After",
      word_count: 2,
      source_file: "next.md",
      split_candidates: [],
    },
  ];

  it("rejects a split index out of range, naming the chapter", () => {
    expect(() => simulateOperations(ITEMS, { splits: { 9: [0] }, merges: [] })).toThrow(
      /chapter 9.*out of range/,
    );
  });

  it("rejects a split ordinal out of range, naming chapter and bound", () => {
    expect(() => simulateOperations(ITEMS, { splits: { 0: [9] }, merges: [] })).toThrow(
      /Split point 9 for chapter 0 is out of range \(0\.\.1\)/,
    );
  });

  it("rejects a negative split ordinal", () => {
    expect(() => simulateOperations(ITEMS, { splits: { 0: [-1] }, merges: [] })).toThrow(
      /Split point -1 for chapter 0 is out of range/,
    );
  });

  it("rejects a merge index out of range (range before contiguity, Core order)", () => {
    expect(() => simulateOperations(ITEMS, { splits: {}, merges: [[0, 5]] })).toThrow(
      /index 5 is out of range/,
    );
  });

  it("rejects a chapter appearing in more than one merge", () => {
    const items: ImportPreviewItem[] = [
      ...ITEMS,
      { index: 2, suggested_title: "C", word_count: 1, source_file: "c.md", split_candidates: [] },
    ];
    expect(() =>
      simulateOperations(items, {
        splits: {},
        merges: [
          [0, 1],
          [1, 2],
        ],
      }),
    ).toThrow(/Chapter 1 appears in more than one merge/);
  });

  it("rejects a split that selects no split points", () => {
    expect(() => simulateOperations(ITEMS, { splits: { 0: [] }, merges: [] })).toThrow(
      /chapter 0 selects no split points/,
    );
  });

  it("rejects a split that repeats a split point", () => {
    expect(() => simulateOperations(ITEMS, { splits: { 0: [0, 0] }, merges: [] })).toThrow(
      /chapter 0 repeats a split point/,
    );
  });

  it("rejects a split on a chapter without candidates (D2a: .txt is merge-only)", () => {
    expect(() => simulateOperations(ITEMS, { splits: { 1: [0] }, merges: [] })).toThrow(
      /chapter 1.*no split candidates/,
    );
  });

  it("rejects a non-contiguous merge, naming the chapter", () => {
    const items: ImportPreviewItem[] = [
      ...ITEMS,
      { index: 2, suggested_title: "C", word_count: 1, source_file: "c.md", split_candidates: [] },
    ];
    expect(() => simulateOperations(items, { splits: {}, merges: [[0, 2]] })).toThrow(
      /not contiguous at chapter 2/,
    );
  });

  it("rejects a chapter that is both split and merged", () => {
    expect(() => simulateOperations(ITEMS, { splits: { 0: [0] }, merges: [[0, 1]] })).toThrow(
      /both split and merged/,
    );
  });

  it("rejects a merge of fewer than two chapters", () => {
    expect(() => simulateOperations(ITEMS, { splits: {}, merges: [[0]] })).toThrow(
      /must combine at least two chapters/,
    );
  });

  it("rejects a split that would remove the chapter entirely", () => {
    const items: ImportPreviewItem[] = [
      {
        index: 0,
        suggested_title: "Whatever",
        word_count: 2,
        source_file: "a.md",
        split_candidates: [{ ordinal: 0, heading: "Only", words_before: 0 }],
      },
    ];
    expect(() => simulateOperations(items, { splits: { 0: [0] }, merges: [] })).toThrow(
      /would remove it entirely/,
    );
  });
});

describe("buildAdjustments", () => {
  it("maps stable keys to FINAL indices and canonicalizes ops", () => {
    const items: ImportPreviewItem[] = [
      {
        index: 0,
        suggested_title: "Long",
        word_count: 11,
        source_file: "long.md",
        split_candidates: [{ ordinal: 0, heading: "Scene A", words_before: 2 }],
      },
      {
        index: 1,
        suggested_title: "After",
        word_count: 2,
        source_file: "next.md",
        split_candidates: [],
      },
    ];
    const file = new File(["x"], "long.md");
    // Split 0 at [0] → final rows: ["0#0" Long-part0, "0#1" Scene A, "1#0" After]
    const selection: ImportSelection = {
      files: [file],
      items,
      ops: { splits: { 0: [0] }, merges: [] },
      excludedKeys: ["0#1"],
      titleByKey: { "0#0": "Intro" },
      includedCount: 2,
    };
    expect(buildAdjustments(selection)).toEqual({
      splits: [{ index: 0, at: [0] }],
      merges: [],
      excluded_indices: [1],
      title_overrides: { "0": "Intro" },
    });
  });

  it("canonicalizes unsorted ops (sorted `at`, sorted runs, ops by index)", () => {
    const items: ImportPreviewItem[] = [
      { index: 0, suggested_title: "A", word_count: 1, source_file: "a.md", split_candidates: [] },
      { index: 1, suggested_title: "B", word_count: 1, source_file: "a.md", split_candidates: [] },
      { index: 2, suggested_title: "C", word_count: 1, source_file: "a.md", split_candidates: [] },
    ];
    const selection: ImportSelection = {
      files: [],
      items,
      ops: { splits: {}, merges: [[2, 1]] },
      excludedKeys: [],
      titleByKey: {},
      includedCount: 3,
    };
    expect(buildAdjustments(selection)).toEqual({
      splits: [],
      merges: [{ indices: [1, 2] }],
      excluded_indices: [],
      title_overrides: {},
    });
  });

  it("canonicalizes multiple ops (splits by index, merges by first index)", () => {
    const items: ImportPreviewItem[] = [
      { index: 0, suggested_title: "A", word_count: 1, source_file: "a.md", split_candidates: [] },
      {
        index: 1,
        suggested_title: "B",
        word_count: 3,
        source_file: "b.md",
        split_candidates: [{ ordinal: 0, heading: "B1", words_before: 1 }],
      },
      { index: 2, suggested_title: "C", word_count: 1, source_file: "c.md", split_candidates: [] },
      { index: 3, suggested_title: "D", word_count: 1, source_file: "d.md", split_candidates: [] },
      {
        index: 4,
        suggested_title: "E",
        word_count: 3,
        source_file: "e.md",
        split_candidates: [{ ordinal: 0, heading: "E1", words_before: 1 }],
      },
    ];
    const selection: ImportSelection = {
      files: [],
      items,
      ops: { splits: { 4: [0], 1: [0] }, merges: [[3, 2]] },
      excludedKeys: [],
      titleByKey: {},
      includedCount: 5,
    };
    expect(buildAdjustments(selection)).toEqual({
      splits: [
        { index: 1, at: [0] },
        { index: 4, at: [0] },
      ],
      merges: [{ indices: [2, 3] }],
      excluded_indices: [],
      title_overrides: {},
    });
  });

  it("sorts multiple merges by first index", () => {
    const items: ImportPreviewItem[] = [
      { index: 0, suggested_title: "A", word_count: 1, source_file: "a.md", split_candidates: [] },
      { index: 1, suggested_title: "B", word_count: 1, source_file: "a.md", split_candidates: [] },
      { index: 2, suggested_title: "C", word_count: 1, source_file: "c.md", split_candidates: [] },
      { index: 3, suggested_title: "D", word_count: 1, source_file: "d.md", split_candidates: [] },
    ];
    const selection: ImportSelection = {
      files: [],
      items,
      ops: {
        splits: {},
        merges: [
          [2, 3],
          [0, 1],
        ],
      },
      excludedKeys: [],
      titleByKey: {},
      includedCount: 4,
    };
    expect(buildAdjustments(selection).merges).toEqual([{ indices: [0, 1] }, { indices: [2, 3] }]);
  });

  it("keeps v1 semantics when no ops and no edits exist", () => {
    const items: ImportPreviewItem[] = [
      { index: 0, suggested_title: "A", word_count: 1, source_file: "a.md", split_candidates: [] },
    ];
    const selection: ImportSelection = {
      files: [],
      items,
      ops: { splits: {}, merges: [] },
      excludedKeys: [],
      titleByKey: {},
      includedCount: 1,
    };
    expect(buildAdjustments(selection)).toEqual({
      splits: [],
      merges: [],
      excluded_indices: [],
      title_overrides: {},
    });
  });
});

describe("serverSupportsOps", () => {
  it("is true when the v2 field is present (even empty)", () => {
    expect(
      serverSupportsOps({
        items: [
          {
            index: 0,
            suggested_title: "A",
            word_count: 1,
            source_file: "a.txt",
            split_candidates: [],
          },
        ],
        file_count: 1,
        chapter_count: 1,
        total_word_count: 1,
      }),
    ).toBe(true);
  });

  it("is false for v1-shaped items (old server, field absent)", () => {
    const legacy = {
      items: [{ index: 0, suggested_title: "A", word_count: 1, source_file: "a.txt" }],
    };
    expect(serverSupportsOps(legacy as never)).toBe(false);
  });
});
