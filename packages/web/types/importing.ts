// Project Import types — RULE-17 mirror of apps/api/narrare/importing/schemas.py
// (vocabulary v2, ADR-091 Amendment 2). ImportSelection / ImportOpsState are
// frontend-only (File objects and stable keys never cross the wire as JSON).
// The v1→v2 transition members (excludedIndices/titleOverrides, optional
// splits/merges) were removed with F1 T7: commit goes through
// buildAdjustments everywhere, so selections are v2-complete by construction.

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
   * Mirror of schemas.ImportCommitAdjustments (vocabulary v2, extra="forbid"):
   * splits/merges address ORIGINAL indices; excluded_indices/title_overrides
   * address FINAL (post-ops) indices. The server defaults absent ops to [],
   * but v2-complete payloads are built exclusively via buildAdjustments.
   */
  splits: ImportSplitOperation[];
  merges: ImportMergeOperation[];
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
 * v2-complete since F1 T7: the panel publishes items/ops/excludedKeys/
 * titleByKey from pick time on (a provisional publish before the preview
 * resolves carries empty items and EMPTY_OPS — commit then sends the
 * identity payload and the server re-parses the raw files anyway).
 */
export interface ImportSelection {
  files: File[];
  /** Preview rows the stable keys bind to (simulation input). */
  items: ImportPreviewItem[];
  /** Split/merge operations in ORIGINAL index space. */
  ops: ImportOpsState;
  /** Excluded rows by stable key `${origIndex}#${part}`. */
  excludedKeys: string[];
  /** Renames by stable key `${origIndex}#${part}`. */
  titleByKey: Record<string, string>;
  includedCount: number;
}
