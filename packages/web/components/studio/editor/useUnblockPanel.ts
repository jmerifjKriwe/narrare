"use client";

/**
 * useUnblockPanel — open/close + interaction state for {@link UnblockPanel} (WRITE-009).
 *
 * Owns the open/close state, the "stuck" description text, the textarea focus
 * ref, and the panel-level effects (Escape-to-close, open-focus, unmount-cancel).
 * Stream lifecycle is delegated to {@link useUnblockStream}. Extracted from
 * {@link UnblockPanel} to keep the component presentational and under the
 * file-size limit (RULE-04 / RULE-06).
 *
 * @module useUnblockPanel
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useUnblockStream } from "./useUnblockStream";

/**
 * @param novelId   Novel to generate suggestions for (SSE URL path parameter).
 * @param chapterId Optional chapter to scope the suggestions (request body).
 * @returns Panel open/close state, handlers, the focus ref, and the stream
 *          lifecycle flags surfaced from {@link useUnblockStream}.
 */
export function useUnblockPanel(novelId: string, chapterId?: string) {
  const [isOpen, setIsOpen] = useState(false);
  const [stuckText, setStuckText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const {
    state: aiState,
    cancel: cancelSuggestions,
    retry: retrySuggestions,
    reset: resetSuggestions,
    request: requestSuggestions,
    isIdle,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  } = useUnblockStream(novelId, chapterId);

  const suggestions = aiState.result;
  const error = aiState.error;
  const isBusy = isLoading || isStreaming;

  const handleOpen = useCallback(() => setIsOpen(true), []);

  const handleClose = useCallback(() => {
    cancelSuggestions();
    setIsOpen(false);
  }, [cancelSuggestions]);

  const handleGetSuggestions = useCallback(() => {
    requestSuggestions(stuckText);
  }, [requestSuggestions, stuckText]);

  const handleDismiss = useCallback(() => {
    // Clear results, return to the input form.
    resetSuggestions();
    setStuckText("");
    textareaRef.current?.focus();
  }, [resetSuggestions]);

  // Escape closes the panel (only while open).
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        handleClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, handleClose]);

  // Focus the textarea when the panel opens.
  useEffect(() => {
    if (!isOpen) return;
    const id = window.setTimeout(() => textareaRef.current?.focus(), 0);
    return () => window.clearTimeout(id);
  }, [isOpen]);

  // Cancel any in-flight stream on unmount.
  useEffect(() => {
    return () => cancelSuggestions();
  }, [cancelSuggestions]);

  return {
    isOpen,
    textareaRef,
    stuckText,
    setStuckText,
    handleOpen,
    handleClose,
    handleGetSuggestions,
    handleDismiss,
    suggestions,
    error,
    isBusy,
    isConnectionLost,
    cancelSuggestions,
    retrySuggestions,
    isIdle,
    isComplete,
    isError,
  };
}
