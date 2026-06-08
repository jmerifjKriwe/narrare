/**
 * Shared utilities and types for the Co-Author panel hook.
 *
 * Extracted from useCoAuthorPanel for modularity (RULE-04).
 *
 * @module coauthor-panel-utils
 */

import type { CoAuthorPhase } from "./coauthor-styles";

// ---------------------------------------------------------------------------
// Hook params
// ---------------------------------------------------------------------------

interface UseCoAuthorPanelParams {
  readonly novelId: string;
  readonly chapterId: string;
  readonly selectionText: string;
  readonly contextBefore?: string;
  readonly contextAfter?: string;
  readonly onAccept: (revisedText: string) => void;
  readonly onClose: () => void;
}

export type { UseCoAuthorPanelParams };

// ---------------------------------------------------------------------------
// Phase computation
// ---------------------------------------------------------------------------

/**
 * Compute the current co-author phase from lifecycle flags and manual override.
 *
 * The manual override takes precedence (e.g., when the user stops mid-stream
 * with partial output, we force "review" mode instead of falling back to
 * the default error/focus phase).
 */
export function computeCoAuthorPhase(
  manualPhase: CoAuthorPhase | null,
  isLoading: boolean,
  isStreaming: boolean,
  isComplete: boolean,
  isError: boolean,
): CoAuthorPhase {
  return (
    manualPhase ??
    (isLoading || isStreaming ? "streaming" : isComplete ? "review" : isError ? "error" : "focus")
  );
}
