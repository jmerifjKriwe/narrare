// packages/web/lib/importing/simulateOperations.ts
/**
 * THE mirrored-semantics module (ADR-091 Amendment 2, spec §6.2).
 *
 * Mirrors packages/core/narrare_core/importing/operations.py — validation
 * outcomes, materialization order, title/word-count rules — and is pinned to
 * Core's outputs by the shared golden fixture
 * (lib/importing/__fixtures__/operations-golden.json) consumed by BOTH pytest
 * and vitest. The server remains the authority: commit re-derives candidates
 * and re-validates every op; displayed word counts are advisory (merge counts
 * are recomputed server-side from the joined content).
 *
 * Pure functions only: no React, no File parsing — operates on preview items
 * and candidate lists. This is the ONE place op semantics are mirrored in TS.
 */

import type {
  ImportCommitAdjustments,
  ImportOpsState,
  ImportPreviewItem,
  ImportPreviewResponse,
  ImportSelection,
} from "@/types";

/** Mirror of Core candidates.SPLIT_CANDIDATES_MAX (preview enrichment cap). */
export const SPLIT_CANDIDATES_MAX = 200;

/** Mirror of the schemas' heading/title max_length (headings become part titles). */
export const TITLE_MAX_LENGTH = 500;

export interface SimulatedRow {
  /** Stable FE key `${origIndex}#${part}` — never sent on the wire. */
  key: string;
  finalIndex: number;
  origIndex: number;
  part: number;
  title: string;
  wordCount: number;
  sourceFile: string;
  isMerged: boolean;
  mergedCount: number;
}

/** Recursively freeze a value in place and return it with its static type. */
function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === "object") {
    Object.freeze(value);
    for (const item of Object.values(value)) deepFreeze(item);
  }
  return value;
}

/**
 * The canonical empty ops state — deep-frozen so it can be shared as a seed
 * or fallback without defensive copies (opsState helpers return new state
 * objects and never mutate their input; buildAdjustments only reads).
 */
export const EMPTY_OPS: ImportOpsState = deepFreeze({ splits: {}, merges: [] });

function countWords(text: string): number {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

/**
 * The stored heading excludes the `###` marker; the heading LINE in the
 * stored content carries exactly one extra token (the marker itself) — so a
 * part's token budget between two bounds loses `1 + words(heading)` tokens.
 */
function headingLineWords(heading: string): number {
  return 1 + countWords(heading);
}

function splitIndexesOf(ops: ImportOpsState): Set<number> {
  return new Set(Object.keys(ops.splits).map(Number));
}

/** Canonical form of a declared merge run — Core sorts before consuming
 *  (order freedom: FE may declare `[3, 2]`, Core canonicalizes). */
function canonicalRun(run: number[]): number[] {
  return [...run].sort((a, b) => a - b);
}

/**
 * Mirror of Core validate_operations — throws on any invalid op, naming the
 * offending op (per-op drift detection: a stale preview surfaces as a
 * targeted error, never a silently wrong import).
 *
 * No duplicate-split check: Core needs one because its input is a list; the
 * FE ImportOpsState keys splits by original index, so duplicates cannot exist.
 */
export function validateOps(items: ImportPreviewItem[], ops: ImportOpsState): void {
  const count = items.length;
  const splitIndexes = splitIndexesOf(ops);

  for (const [key, at] of Object.entries(ops.splits)) {
    const index = Number(key);
    if (!(index >= 0 && index < count)) {
      throw new Error(
        `Split for chapter ${index}: index ${index} is out of range (0..${count - 1}).`,
      );
    }
    if (at.length === 0) {
      throw new Error(`Split for chapter ${index} selects no split points.`);
    }
    if (new Set(at).size !== at.length) {
      throw new Error(`Split for chapter ${index} repeats a split point.`);
    }
    const candidates = items[index].split_candidates ?? [];
    if (candidates.length === 0) {
      throw new Error(
        `Split for chapter ${index} selects split points, but the chapter has no split candidates.`,
      );
    }
    const min = Math.min(...at);
    const max = Math.max(...at);
    if (min < 0 || max >= candidates.length) {
      const offender = min < 0 ? min : max;
      throw new Error(
        `Split point ${offender} for chapter ${index} is out of range (0..${candidates.length - 1}).`,
      );
    }
  }

  const merged = new Set<number>();
  for (const run of ops.merges) {
    const declared = `Merge [${run.join(", ")}]`;
    if (run.length < 2) {
      throw new Error(`${declared} must combine at least two chapters.`);
    }
    const indices = canonicalRun(run);
    for (let position = 0; position < indices.length; position++) {
      const index = indices[position];
      if (!(index >= 0 && index < count)) {
        throw new Error(`${declared}: index ${index} is out of range (0..${count - 1}).`);
      }
      if (position > 0 && index !== indices[position - 1] + 1) {
        throw new Error(`${declared} is not contiguous at chapter ${index}.`);
      }
      if (merged.has(index)) {
        throw new Error(`Chapter ${index} appears in more than one merge.`);
      }
      if (splitIndexes.has(index)) {
        throw new Error(`Chapter ${index} cannot be both split and merged.`);
      }
      merged.add(index);
    }
  }
}

/** Mirror of Core apply_operations (the golden fixture pins the parity). */
export function simulateOperations(
  items: ImportPreviewItem[],
  ops: ImportOpsState,
): SimulatedRow[] {
  validateOps(items, ops);

  const splitAt = new Map<number, number[]>();
  for (const [key, at] of Object.entries(ops.splits)) {
    splitAt.set(
      Number(key),
      [...at].sort((a, b) => a - b),
    );
  }
  const mergeRoot = new Map<number, number>();
  const mergeMembers = new Map<number, number[]>();
  for (const run of ops.merges) {
    const members = canonicalRun(run);
    mergeMembers.set(members[0], members);
    for (const index of members) mergeRoot.set(index, members[0]);
  }

  const rows: SimulatedRow[] = [];
  const push = (row: Omit<SimulatedRow, "finalIndex">) => {
    rows.push({ ...row, finalIndex: rows.length });
  };

  items.forEach((item, index) => {
    const root = mergeRoot.get(index);
    if (root !== undefined) {
      const members = mergeMembers.get(root);
      if (index === root && members !== undefined) {
        // D5a: title/status/source come from the FIRST constituent; contents
        // join with one blank line server-side. The word count is RECOMPUTED
        // from the joined content there — the sum is the advisory FE stand-in
        // (equal for honest counts; the golden fixture pins it).
        push({
          key: `${index}#0`,
          origIndex: index,
          part: 0,
          title: item.suggested_title,
          wordCount: members.reduce((sum, i) => sum + items[i].word_count, 0),
          sourceFile: item.source_file,
          isMerged: true,
          mergedCount: members.length,
        });
      }
      return;
    }
    const cuts = splitAt.get(index);
    if (cuts === undefined) {
      push({
        key: `${index}#0`,
        origIndex: index,
        part: 0,
        title: item.suggested_title,
        wordCount: item.word_count,
        sourceFile: item.source_file,
        isMerged: false,
        mergedCount: 1,
      });
      return;
    }
    const candidates = item.split_candidates ?? [];
    const selected = cuts.map((ordinal) => candidates[ordinal]);
    let partsPushed = 0;
    for (let j = 0; j <= selected.length; j++) {
      let wordCount: number;
      if (j === 0) {
        wordCount = selected[0].words_before;
      } else {
        const nextBound = j < selected.length ? selected[j].words_before : item.word_count;
        wordCount =
          nextBound - selected[j - 1].words_before - headingLineWords(selected[j - 1].heading);
      }
      if (wordCount <= 0) continue; // empty part dropped (v1 rule, mirrored)
      push({
        key: `${index}#${j}`,
        origIndex: index,
        part: j,
        title: j === 0 ? item.suggested_title : selected[j - 1].heading.slice(0, TITLE_MAX_LENGTH),
        wordCount,
        sourceFile: item.source_file,
        isMerged: false,
        mergedCount: 1,
      });
      partsPushed++;
    }
    if (partsPushed === 0) {
      // Mirror of Core: a split that leaves no part would delete the chapter.
      throw new Error(`Split for chapter ${index} would remove it entirely (no part has content).`);
    }
  });
  return rows;
}

/**
 * The ONE place mapping stable-key edit state to the wire payload:
 * excluded/renames land in FINAL space; ops are canonicalized (sorted) —
 * Core would canonicalize anyway, but sending the canonical form keeps the
 * payload reviewable. TRANSITION: tolerates selections without v2 members
 * (identity adjustments) until the panel produces them (plan T5/T6).
 */
export function buildAdjustments(selection: ImportSelection): ImportCommitAdjustments {
  const ops = selection.ops ?? EMPTY_OPS;
  const rows = simulateOperations(selection.items ?? [], ops);
  const excludedKeys = new Set(selection.excludedKeys ?? []);
  const titleByKey = selection.titleByKey ?? {};
  const excluded_indices: number[] = [];
  const title_overrides: Record<string, string> = {};
  for (const row of rows) {
    if (excludedKeys.has(row.key)) excluded_indices.push(row.finalIndex);
    const title = titleByKey[row.key];
    if (title !== undefined) title_overrides[String(row.finalIndex)] = title;
  }
  const splits = Object.entries(ops.splits)
    .map(([key, at]) => ({ index: Number(key), at: [...at].sort((a, b) => a - b) }))
    .sort((a, b) => a.index - b.index);
  const merges = ops.merges
    .map((run) => ({ indices: canonicalRun(run) }))
    .sort((a, b) => a.indices[0] - b.indices[0]);
  return { splits, merges, excluded_indices, title_overrides };
}

/** Capability probe (spec §7): v2 servers always serialize the field — its
 *  absence on the first item means a v1 server (ops UI must stay gated off). */
export function serverSupportsOps(preview: ImportPreviewResponse): boolean {
  const first = preview.items[0];
  return first !== undefined && "split_candidates" in first;
}
