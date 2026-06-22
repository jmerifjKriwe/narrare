"use client";

import type { ReactNode } from "react";
import { AIDiffSegmentList } from "@/components/shared/ai-diff/AIDiffSegmentList";
import { segmentize } from "@/lib/ai-diff/segmentize";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface InlineDiffProps {
  readonly original: string;
  readonly alternative: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Inline text-only diff facade (CR-AUFG-07-18).
 *
 * Delegates to the shared {@link segmentize} algorithm (single source of the
 * diff logic — DRY) and the accessible {@link AIDiffSegmentList} renderer
 * (`<ins>`/`<del>` + visible markers + sr-only labels — never color alone).
 *
 * This is a low-level inline-text primitive, kept distinct from the full
 * {@link AIDiffView} review surface which additionally renders state badges,
 * provisional indicators, and field-mode columns. Callers that need the full
 * author-control review UI should use `AIDiffView` directly with a domain
 * adapter from `lib/ai-diff/adapters/`.
 */
export function InlineDiff({ original, alternative }: InlineDiffProps) {
  const segments = segmentize(original, alternative);
  return <AIDiffSegmentList segments={segments} />;
}

// ---------------------------------------------------------------------------
// Back-compat export
// ---------------------------------------------------------------------------

/**
 * Return the diff as a flat array of React spans.
 *
 * @deprecated Prefer `<InlineDiff>` (accessible `<ins>`/`<del>`) or compose
 *   `segmentize()` + `<AIDiffSegmentList>` directly. Retained because
 *   `__tests__/InlineDiff.test.ts` still exercises this export; migrate that
 *   suite to the shared primitive in a follow-up. The returned spans carry no
 *   change-type semantics — they are plain text wrappers for legacy callers.
 */
export function computeDiffElements(original: string, alternative: string): ReactNode[] {
  return segmentize(original, alternative).map((seg, i) => {
    // Composite key: kind + index guarantees uniqueness even when consecutive
    // segments share identical text (matches AIDiffSegmentList's key strategy).
    const key = `${seg.kind}-${i}`;
    return <span key={key}>{seg.text}</span>;
  });
}
