"use client";

import DiffMatchPatch from "diff-match-patch";
import type { ReactNode } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface InlineDiffProps {
  readonly original: string;
  readonly alternative: string;
}

// ---------------------------------------------------------------------------
// Singleton dmp instance (reused across calls)
// ---------------------------------------------------------------------------

const dmp = new DiffMatchPatch();

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Compute inline diff between original and alternative text.
 *
 * Returns React elements with:
 * - Green background for additions
 * - Red background + strikethrough for removals
 * - Normal text for unchanged content
 */
export function computeDiffElements(original: string, alternative: string): ReactNode[] {
  const diffs = dmp.diff_main(original, alternative);
  dmp.diff_cleanupSemantic(diffs);

  const elements: ReactNode[] = [];
  let key = 0;

  for (const [operation, text] of diffs) {
    if (operation === DiffMatchPatch.DIFF_INSERT) {
      elements.push(
        <span
          key={`ins-${key++}`}
          className="bg-green-200/60 dark:bg-green-900/40 rounded-sm px-0.5"
        >
          {text}
        </span>,
      );
    } else if (operation === DiffMatchPatch.DIFF_DELETE) {
      elements.push(
        <span
          key={`del-${key++}`}
          className="bg-red-200/60 dark:bg-red-900/40 line-through rounded-sm px-0.5"
        >
          {text}
        </span>,
      );
    } else {
      elements.push(<span key={`eq-${key++}`}>{text}</span>);
    }
  }

  return elements;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function InlineDiff({ original, alternative }: InlineDiffProps) {
  const diffElements = computeDiffElements(original, alternative);
  return <>{diffElements}</>;
}
