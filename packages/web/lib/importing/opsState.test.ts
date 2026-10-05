/**
 * Op-state helper tests (FE ergonomics; the server re-validates all ops at
 * commit — these helpers just make it hard to construct an invalid set from
 * the UI). All helpers operate in ORIGINAL index space, return NEW state
 * objects, and never mutate their input — pinned here because the shared
 * EMPTY_OPS seed is deep-frozen (rider: immutability semantics).
 */

import type { ImportOpsState, ImportPreviewItem } from "@/types";
import {
  applySplit,
  canMergeWithNext,
  clearSplit,
  EMPTY_OPS,
  mergeWithNext,
  unmergeAt,
} from "./opsState";
import { EMPTY_OPS as SHIPPED_EMPTY_OPS } from "./simulateOperations";

const ITEMS: ImportPreviewItem[] = [
  {
    index: 0,
    suggested_title: "Long",
    word_count: 6,
    source_file: "long.md",
    split_candidates: [{ ordinal: 0, heading: "S1", words_before: 2 }],
  },
  { index: 1, suggested_title: "B", word_count: 1, source_file: "b.md", split_candidates: [] },
  { index: 2, suggested_title: "C", word_count: 1, source_file: "c.md", split_candidates: [] },
];

const EMPTY: ImportOpsState = { splits: {}, merges: [] };

describe("opsState", () => {
  it("applySplit stores sorted cut ordinals; clearSplit removes them", () => {
    const split = applySplit(EMPTY, 0, [1, 0]);
    expect(split.splits[0]).toEqual([0, 1]);
    expect(clearSplit(split, 0).splits[0]).toBeUndefined();
  });

  it("applySplit/clearSplit leave the input state untouched (pure)", () => {
    const input: ImportOpsState = { splits: { 2: [0] }, merges: [] };
    const split = applySplit(input, 0, [0]);
    expect(split).not.toBe(input);
    expect(input.splits[0]).toBeUndefined();
    const cleared = clearSplit(split, 2);
    expect(split.splits[2]).toEqual([0]); // clearSplit only removes the asked index
    expect(cleared.splits).toEqual({ 0: [0] });
  });

  it("mergeWithNext creates then extends a contiguous run", () => {
    const one = mergeWithNext(EMPTY, 1, ITEMS);
    expect(one.merges).toEqual([[1, 2]]);
    const two = mergeWithNext(one, 0, ITEMS);
    expect(two.merges).toEqual([[0, 1, 2]]);
  });

  it("mergeWithNext coalesces adjacent runs", () => {
    const start: ImportOpsState = { splits: {}, merges: [[0, 1]] };
    expect(mergeWithNext(start, 2, ITEMS).merges).toEqual([[0, 1, 2]]);
  });

  it("mergeWithNext coalesces two separate runs via their gap chapter", () => {
    // Runs are atomic (validateOps rejects overlaps): absorbing the run at
    // the gap coalesces BOTH runs — [0,1] + gap 2 + [2,3] → [0,1,2,3].
    const items: ImportPreviewItem[] = [
      ...ITEMS,
      { index: 3, suggested_title: "D", word_count: 1, source_file: "d.md", split_candidates: [] },
    ];
    const start: ImportOpsState = {
      splits: {},
      merges: [
        [0, 1],
        [2, 3],
      ],
    };
    expect(mergeWithNext(start, 1, items).merges).toEqual([[0, 1, 2, 3]]);
  });

  it("mergeWithNext refuses when the next chapter is split (split∩merge=∅)", () => {
    const split: ImportOpsState = { splits: { 1: [0] }, merges: [] };
    expect(mergeWithNext(split, 0, ITEMS)).toBe(split);
  });

  it("mergeWithNext refuses when the clicked chapter is split itself", () => {
    const split: ImportOpsState = { splits: { 0: [0] }, merges: [] };
    expect(mergeWithNext(split, 0, ITEMS)).toBe(split);
  });

  it("mergeWithNext is a no-op at the end of the list (identity preserved)", () => {
    expect(mergeWithNext(EMPTY, 2, ITEMS)).toBe(EMPTY);
  });

  it("unmergeAt removes only the run containing the index", () => {
    const ops: ImportOpsState = {
      splits: {},
      merges: [
        [0, 1],
        [3, 4],
      ],
    };
    expect(unmergeAt(ops, 1).merges).toEqual([[3, 4]]);
  });

  it("canMergeWithNext encodes the UI gating rules", () => {
    expect(canMergeWithNext(ITEMS, EMPTY, 0)).toBe(true);
    expect(canMergeWithNext(ITEMS, EMPTY, 2)).toBe(false); // no next chapter
    expect(canMergeWithNext(ITEMS, { splits: { 1: [0] }, merges: [] }, 0)).toBe(false); // next is split
    expect(canMergeWithNext(ITEMS, { splits: { 0: [0] }, merges: [] }, 0)).toBe(false); // self is split
  });

  it("canMergeWithNext stays truthful for run-extension merges", () => {
    // mergeWithNext({merges: [[0, 1]]}, 2) grows the run to [0, 1, 2] — the
    // gate must say true for exactly the states where the mutation acts.
    expect(canMergeWithNext(ITEMS, { splits: {}, merges: [[0, 1]] }, 2)).toBe(true);
    expect(canMergeWithNext(ITEMS, { splits: {}, merges: [[0, 1]] }, 1)).toBe(true);
    // …but a split chapter right of the run still blocks it.
    expect(canMergeWithNext(ITEMS, { splits: { 2: [0] }, merges: [[0, 1]] }, 1)).toBe(false);
  });
});

describe("EMPTY_OPS (deep-frozen shared seed)", () => {
  it("is the same singleton simulateOperations exports (one definition point)", () => {
    expect(EMPTY_OPS).toBe(SHIPPED_EMPTY_OPS);
  });

  it("is frozen at every level (state object, splits record, merges array)", () => {
    expect(Object.isFrozen(EMPTY_OPS)).toBe(true);
    expect(Object.isFrozen(EMPTY_OPS.splits)).toBe(true);
    expect(Object.isFrozen(EMPTY_OPS.merges)).toBe(true);
  });

  it("rejects mutation attempts (freeze throws in strict mode)", () => {
    expect(() => EMPTY_OPS.merges.push([0, 1])).toThrow(TypeError);
    expect(() => {
      EMPTY_OPS.splits[0] = [0];
    }).toThrow(TypeError);
    expect(() => EMPTY_OPS.merges.shift()).toThrow(TypeError);
  });

  it("stays pristine when helpers consume it (purity contract)", () => {
    applySplit(EMPTY_OPS, 0, [0]);
    clearSplit(EMPTY_OPS, 0);
    mergeWithNext(EMPTY_OPS, 0, ITEMS);
    unmergeAt(EMPTY_OPS, 0);
    expect(EMPTY_OPS.splits).toEqual({});
    expect(EMPTY_OPS.merges).toEqual([]);
  });
});
