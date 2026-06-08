"use client";

/**
 * Co-Author panel hook — manages the co-author SSE lifecycle via useAIOperation.
 *
 * Replaces the previous manual AbortController + startCoAuthorStreaming pattern
 * with the shared AI operation primitive (§16, ADR-043).
 *
 * On success, transitions to review mode with per-change accept/reject.
 * On stop/cancel, preserves partial output for user review.
 * Structured AIErrorResponse replaces raw error.message.
 */

import { useTranslations } from "next-intl";
import { useState } from "react";
import type { CoAuthorRevision } from "@/lib/api/coauthor";
import { getCoAuthorPhaseLabel } from "./coauthor-message-utils";
import { computeCoAuthorPhase, type UseCoAuthorPanelParams } from "./coauthor-panel-utils";
import { useCoAuthorApply } from "./useCoAuthorApply";
import { useCoAuthorHandlers } from "./useCoAuthorHandlers";
import { useCoAuthorReviewState } from "./useCoAuthorReviewState";
import { useCoAuthorStream } from "./useCoAuthorStream";

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useCoAuthorPanel({
  novelId,
  chapterId,
  selectionText,
  contextBefore,
  contextAfter,
  onAccept,
  onClose,
}: UseCoAuthorPanelParams) {
  const t = useTranslations("studio");
  const [submitting, setSubmitting] = useState(false);
  const [localErrorMsg, setLocalErrorMsg] = useState<string | null>(null);

  const {
    selectedFocus,
    changes,
    acceptance,
    setChanges,
    setAcceptance,
    toggleFocus,
    handleAcceptAll,
    handleRejectAll,
    handleToggleChange,
  } = useCoAuthorReviewState();

  const {
    streamedText,
    reasoning,
    requestId,
    state,
    start,
    cancel,
    retry,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  } = useCoAuthorStream({
    novelId,
    chapterId,
    selectionText,
    contextBefore,
    contextAfter,
    selectedFocus,
    setChanges,
    setAcceptance,
    onSuccess: (revision: CoAuthorRevision) => {
      setManualPhase(revision.changes.length > 0 ? "review" : "done");
    },
  });

  const { manualPhase, setManualPhase, handleStart, handleCancel, handleStop, handleRetry } =
    useCoAuthorHandlers({
      selectedFocus,
      streamedText,
      onClose,
      start,
      cancel,
      retry,
    });

  const handleApply = useCoAuthorApply({
    changes,
    acceptance,
    streamedText,
    requestId,
    chapterId,
    novelId,
    selectionText,
    onAccept,
    setPhase: (p) => {
      setManualPhase(p);
      if (p !== "error") setLocalErrorMsg(null);
    },
    setSubmitting,
    setErrorMsg: (msg) => setLocalErrorMsg(msg),
    errorGeneric: t("coAuthor.errorGeneric"),
  });

  // Merge useAIOperation lifecycle with manual phase overrides (stop-with-output)
  const phase = computeCoAuthorPhase(manualPhase, isLoading, isStreaming, isComplete, isError);

  const phaseLabel = getCoAuthorPhaseLabel(phase, t);

  return {
    phase,
    selectedFocus,
    streamedText,
    changes,
    reasoning,
    submitting,
    acceptance,
    /** Structured AIErrorResponse from useAIOperation (null when no error). */
    error: state.error,
    /** User-visible error message string (null when no error). */
    errorMsg: state.error?.userMessage ?? localErrorMsg,
    isConnectionLost,
    phaseLabel,
    t,
    toggleFocus,
    handleStart,
    handleAcceptAll,
    handleRejectAll,
    handleToggleChange,
    handleApply,
    handleCancel,
    handleStop,
    handleRetry,
  } as const;
}
