"use client";

/**
 * Co-Author panel handler callbacks.
 *
 * Extracts manual phase management and action handlers from useCoAuthorPanel
 * for modularity (RULE-04).
 *
 * @module useCoAuthorHandlers
 */

import { useCallback, useState } from "react";

import type { CoAuthorPhase } from "./coauthor-styles";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UseCoAuthorHandlersParams {
  readonly selectedFocus: readonly string[];
  readonly streamedText: string;
  readonly onClose: () => void;
  readonly start: () => void;
  readonly cancel: () => void;
  readonly retry: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Manages manual phase overrides and action handlers for the Co-Author panel.
 *
 * Owns the `manualPhase` state so handler callbacks can update it without
 * circular dependencies on useAIOperation lifecycle.
 */
export function useCoAuthorHandlers({
  selectedFocus,
  streamedText,
  onClose,
  start,
  cancel,
  retry,
}: UseCoAuthorHandlersParams) {
  const [manualPhase, setManualPhase] = useState<CoAuthorPhase | null>(null);

  const handleStart = useCallback(() => {
    if (selectedFocus.length === 0) return;
    setManualPhase(null);
    start();
  }, [selectedFocus, start]);

  const handleCancel = useCallback(() => {
    cancel();
    setManualPhase(null);
    onClose();
  }, [cancel, onClose]);

  const handleStop = useCallback(() => {
    cancel();
    setManualPhase(streamedText.trim().length > 0 ? "review" : "focus");
  }, [cancel, streamedText]);

  const handleRetry = useCallback(() => {
    setManualPhase(null);
    retry();
  }, [retry]);

  return { manualPhase, setManualPhase, handleStart, handleCancel, handleStop, handleRetry };
}
