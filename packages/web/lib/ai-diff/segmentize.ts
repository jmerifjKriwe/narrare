import DiffMatchPatch from "diff-match-patch";
import type { AIDiffSegment, AIDiffSegmentKind } from "./contracts";

// Singleton — reused across calls (mirrors the prior InlineDiff instance).
const dmp = new DiffMatchPatch();

/**
 * Pure diff: returns ordered {@link AIDiffSegment}s mapping `original` -> `suggested`.
 *
 * No React, no side effects. This is the single source of the diff algorithm
 * (DRY): `InlineDiff` and the shared adapters all depend on it.
 */
export function segmentize(original: string, suggested: string): AIDiffSegment[] {
  const diffs = dmp.diff_main(original, suggested);
  dmp.diff_cleanupSemantic(diffs);

  const segments: AIDiffSegment[] = [];
  for (const [operation, text] of diffs) {
    const kind: AIDiffSegmentKind =
      operation === DiffMatchPatch.DIFF_INSERT
        ? "added"
        : operation === DiffMatchPatch.DIFF_DELETE
          ? "removed"
          : "unchanged";
    segments.push({ kind, text });
  }
  return segments;
}
