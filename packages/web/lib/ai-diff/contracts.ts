/**
 * CR-AUFG-07-18 — Shared, domain-agnostic AI diff vocabulary.
 *
 * Frontend-only contract (RULE-03): defined BEFORE any component or adapter.
 * The diff primitive is a pure VIEW — it never starts AI work and owns no
 * lifecycle. Lifecycle/cancel/error stay with the source AI operation
 * (ADR-043 useAIOperation).
 */

/** Author-control / acceptance state of an AI diff. */
export type AIDiffState =
  | "suggested" // AI proposal pending an author decision
  | "accepted" // author accepted
  | "rejected" // author rejected
  | "unchanged"; // original and suggested are equal

/** Kind of a single text-level diff segment. */
export type AIDiffSegmentKind = "added" | "removed" | "unchanged";

/** Rendering mode for the view model. */
export type AIDiffMode = "text" | "field";

/** One atomic piece of an inline text diff. Immutable. */
export interface AIDiffSegment {
  readonly kind: AIDiffSegmentKind;
  readonly text: string;
}

/**
 * Shared view model for "AI changed A -> B".
 *
 * - `text` mode: inline character/word diff via `segments` (Rewrite, Co-Author).
 * - `field` mode: whole-value before/after, NO inline diff (KB Enhance) —
 *   structured fields must not be treated as prose diffs (CR-AUFG-07-18 AC #3).
 *   Invariant: `mode === "field"` => `segments` is empty.
 */
export interface AIDiffViewModel {
  /** Stable id (change id, field key, suggestion index, ...). */
  readonly id: string;
  readonly mode: AIDiffMode;
  /** `text` mode: segmented diff; `field` mode: empty array. */
  readonly segments: readonly AIDiffSegment[];
  /** Whole original value. */
  readonly originalFull: string;
  /** Whole suggested value. */
  readonly suggestedFull: string;
  /** Optional domain label (change_type, field label). `null` when N/A. */
  readonly label: string | null;
  /** True while the source operation is still streaming (provisional output). */
  readonly provisional: boolean;
}
