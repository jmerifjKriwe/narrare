// packages/web/lib/importing/opsState.ts
/**
 * Pure FE op-state helpers (ADR-091 Amendment 2, F1 plan Task 5).
 *
 * All operations live in ORIGINAL index space — the same space preview items
 * and the stable `${origIndex}#${part}` row keys (simulateOperations) are
 * built from. Every helper returns a NEW state object and never mutates its
 * input, so the deep-frozen EMPTY_OPS seed is safe to pass around (and to
 * use as a React state initial value).
 *
 * Ergonomics only: these helpers make it hard to construct an invalid set
 * from the UI — they enforce on construction exactly the rules the server
 * re-validates at commit (see validateOps): splits and merges stay disjoint
 * (split∩merge=∅), merge runs stay contiguous and ≥ 2 chapters.
 */

import type { ImportOpsState, ImportPreviewItem } from "@/types";

/** ONE definition point lives in simulateOperations (shipped); re-exported
 *  here as the ops-state seed so consumers need only this module. */
export { EMPTY_OPS } from "./simulateOperations";

function splitIndexesOf(ops: ImportOpsState): Set<number> {
  return new Set(Object.keys(ops.splits).map(Number));
}

/** Canonical form: runs sorted internally, ordered by first index, adjacent
 *  runs joined — the invariant validateOps/simulateOperations rely on. */
function coalesce(runs: number[][]): number[][] {
  const sorted = runs.map((run) => [...run].sort((a, b) => a - b)).sort((a, b) => a[0] - b[0]);
  const out: number[][] = [];
  for (const run of sorted) {
    const last = out[out.length - 1];
    if (last && run[0] <= last[last.length - 1] + 1) last.push(...run);
    else out.push([...run]);
  }
  return out;
}

/** The run a merge click on `index` grows: the run containing `index`, else
 *  the run ending directly before it (coalescing case), else a fresh
 *  singleton (which must never be stored unless it grows). */
function growingRun(runs: number[][], index: number): number[] | undefined {
  return runs.find((run) => run.includes(index)) ?? runs.find((run) => run.includes(index - 1));
}

/** Split original chapter `index` at the given candidate ordinals (stored
 *  sorted; `at` itself is not aliased). */
export function applySplit(ops: ImportOpsState, index: number, at: number[]): ImportOpsState {
  return { ...ops, splits: { ...ops.splits, [index]: [...at].sort((a, b) => a - b) } };
}

/** Remove the split of original chapter `index`; all other splits are kept. */
export function clearSplit(ops: ImportOpsState, index: number): ImportOpsState {
  const splits = { ...ops.splits };
  delete splits[index];
  return { ...ops, splits };
}

/**
 * Merge original chapter `index` with the chapter after its block's tail:
 * creates a run, extends an existing one, or coalesces adjacent runs.
 * Returns the SAME state object (identity no-op) when `index` is split,
 * when the next chapter is split (split∩merge=∅), or when there is no next
 * chapter — so state consumers can rely on reference inequality to detect
 * actual change.
 */
export function mergeWithNext(
  ops: ImportOpsState,
  index: number,
  items: ImportPreviewItem[],
): ImportOpsState {
  const splitIndexes = splitIndexesOf(ops);
  if (splitIndexes.has(index)) return ops;
  const runs = ops.merges.map((run) => [...run]);
  const found = growingRun(runs, index);
  const run = found ?? [index];
  if (found === undefined) runs.push(run);
  const next = run[run.length - 1] + 1;
  if (next > items.length - 1 || splitIndexes.has(next)) return ops;
  const other = runs.find((candidate) => candidate !== run && candidate.includes(next));
  if (other) {
    run.push(...other);
    runs.splice(runs.indexOf(other), 1);
  } else {
    run.push(next);
  }
  return { ...ops, merges: coalesce(runs) };
}

/** Dissolve the entire merge run containing original chapter `index`. */
export function unmergeAt(ops: ImportOpsState, index: number): ImportOpsState {
  return { ...ops, merges: ops.merges.filter((run) => !run.includes(index)) };
}

/**
 * UI gate mirroring mergeWithNext's preconditions exactly: false when
 * `index` or the next chapter after its block's tail is split, or when that
 * tail is the last chapter — i.e. canMergeWithNext(…) is true precisely
 * when mergeWithNext(…) would return a new state.
 */
export function canMergeWithNext(
  items: ImportPreviewItem[],
  ops: ImportOpsState,
  index: number,
): boolean {
  const splitIndexes = splitIndexesOf(ops);
  if (splitIndexes.has(index)) return false;
  const found = growingRun(ops.merges, index);
  const tail = found === undefined ? index : found[found.length - 1];
  const next = tail + 1;
  return next <= items.length - 1 && !splitIndexes.has(next);
}
