// Project Import types — RULE-17 mirror of apps/api/narrare/importing/schemas.py
// (vocabulary v2, ADR-091 Amendment 2). ImportSelection / ImportOpsState are
// frontend-only (File objects and stable keys never cross the wire as JSON).
//
// TRANSITION (F1 plan): ImportSelection and ImportCommitAdjustments keep
// their v1 members next to the new v2 members so the live panel/Modal/wizard
// keep compiling unchanged. The panel ops UI starts producing the v2 members
// (plan T5/T6); the v1 members are removed when commit migrates to
// buildAdjustments (plan T7 "final sweep": no excludedIndices/titleOverrides
// left anywhere).

/** Mirror of schemas.ImportSplitCandidate (cap ≤ 200 candidates). */
export interface ImportSplitCandidate {
  ordinal: number;
  heading: string;
  words_before: number;
}

export interface ImportPreviewItem {
  index: number;
  suggested_title: string;
  word_count: number;
  source_file: string;
  /**
   * Mirror of schemas.ImportPreviewItem.split_candidates — v2 servers always
   * serialize it. Optional here because v1 servers omit the field entirely;
   * the version-skew probe (serverSupportsOps) keys on exactly that absence.
   */
  split_candidates?: ImportSplitCandidate[];
}

export interface ImportPreviewResponse {
  items: ImportPreviewItem[];
  file_count: number;
  chapter_count: number;
  total_word_count: number;
}

/** Mirror of schemas.ImportSplitOperation — split chapter `index` at the given candidate ordinals. */
export interface ImportSplitOperation {
  index: number;
  at: number[];
}

/** Mirror of schemas.ImportMergeOperation — merge a contiguous run of original chapters (≥ 2). */
export interface ImportMergeOperation {
  indices: number[];
}

export interface ImportCommitAdjustments {
  /**
   * Vocabulary v2 (schemas.ImportCommitAdjustments, extra="forbid"):
   * splits/merges address ORIGINAL indices; excluded_indices/title_overrides
   * address FINAL (post-ops) indices. splits/merges are optional during the
   * v1→v2 transition — current callers send v1 payloads, which the server
   * accepts and defaults to [].
   */
  splits?: ImportSplitOperation[];
  merges?: ImportMergeOperation[];
  excluded_indices: number[];
  title_overrides: Record<string, string>;
}

export interface ImportCommitChapterInfo {
  id: string;
  title: string;
  position: number;
  word_count: number;
}

export interface ImportCommitResponse {
  novel_id: string;
  created_count: number;
  first_position: number;
  last_position: number;
  chapters: ImportCommitChapterInfo[];
}

/** Operation state in ORIGINAL index space (FE-only wire-precursor). */
export interface ImportOpsState {
  /** origIndex → selected candidate ordinals (unsorted input allowed). */
  splits: Record<number, number[]>;
  /** Each run combines ≥ 2 contiguous original indices (unsorted input allowed). */
  merges: number[][];
}

/**
 * Current pick state of the shared import panel (frontend-only).
 * TRANSITION: the v2 members (items/ops/excludedKeys/titleByKey) are optional
 * until the panel produces them (plan T5/T6); the v1 members
 * (excludedIndices/titleOverrides) disappear once commit goes through
 * buildAdjustments (plan T7).
 */
export interface ImportSelection {
  files: File[];
  /** v1 (until T7): exclusions keyed by ORIGINAL index — with no ops, final == original. */
  excludedIndices: number[];
  /** v1 (until T7): renames keyed by ORIGINAL index as string. */
  titleOverrides: Record<string, string>;
  /** v2: preview rows the stable keys bind to (simulation input). */
  items?: ImportPreviewItem[];
  /** v2: split/merge operations in ORIGINAL index space. */
  ops?: ImportOpsState;
  /** v2: excluded rows by stable key `${origIndex}#${part}`. */
  excludedKeys?: string[];
  /** v2: renames by stable key `${origIndex}#${part}`. */
  titleByKey?: Record<string, string>;
  includedCount: number;
}
