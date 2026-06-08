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
import { useCallback, useState } from "react";
import { type CoAuthorRevision, streamCoAuthor } from "@/lib/api/coauthor";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { createAcceptanceMap, getCoAuthorPhaseLabel } from "./coauthor-message-utils";
import type { CoAuthorPhase } from "./coauthor-styles";
import { useCoAuthorApply } from "./useCoAuthorApply";
import { useCoAuthorReviewState } from "./useCoAuthorReviewState";

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
  const [streamedText, setStreamedText] = useState("");
  const [reasoning, setReasoning] = useState("");
  const [requestId, setRequestId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [manualPhase, setManualPhase] = useState<CoAuthorPhase | null>(null);
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
    state,
    start,
    cancel,
    notifyData,
    retry,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  } = useAIOperation<CoAuthorRevision | null>({
    execute: async (signal) => {
      setStreamedText("");
      setChanges([]);
      setReasoning("");
      setRequestId(crypto.randomUUID());

      let revision: CoAuthorRevision | null = null;

      await streamCoAuthor(
        chapterId,
        novelId,
        {
          selection_text: selectionText,
          context_before: contextBefore,
          context_after: contextAfter,
          focus: [...selectedFocus],
        },
        {
          onChunk: (text) => {
            notifyData();
            setStreamedText((prev) => prev + text);
          },
          onComplete: (rev) => {
            revision = rev;
            setChanges(rev.changes);
            setReasoning(rev.reasoning);
            if (rev.request_id) setRequestId(rev.request_id);
            setAcceptance(createAcceptanceMap(rev.changes, true));
          },
          onError: (err) => {
            throw err;
          },
        },
        signal,
      );

      return revision;
    },
    onSuccess: (revision) => {
      if (revision) {
        setManualPhase(revision.changes.length > 0 ? "review" : "done");
      }
    },
    connectionLossTimeout: 15_000,
  });

  // Merge useAIOperation lifecycle with manual phase overrides (stop-with-output)
  const phase: CoAuthorPhase =
    manualPhase ??
    (isLoading || isStreaming ? "streaming" : isComplete ? "review" : isError ? "error" : "focus");

  const handleStart = useCallback(() => {
    if (selectedFocus.length === 0) return;
    setManualPhase(null);
    start();
  }, [selectedFocus, start]);

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
