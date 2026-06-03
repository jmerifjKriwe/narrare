"use client";

import { useTranslations } from "next-intl";
import { useCallback, useRef, useState } from "react";

import { getCoAuthorPhaseLabel } from "./coauthor-message-utils";
import { startCoAuthorStreaming } from "./coauthor-streaming";
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
  const [phase, setPhase] = useState<CoAuthorPhase>("focus");
  const [streamedText, setStreamedText] = useState("");
  const [reasoning, setReasoning] = useState("");
  const [requestId, setRequestId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
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

  const handleStart = useCallback(() => {
    if (selectedFocus.length === 0) return;
    startCoAuthorStreaming({
      novelId,
      chapterId,
      selectionText,
      contextBefore,
      contextAfter,
      selectedFocus,
      errorGeneric: t("coAuthor.errorGeneric"),
      abortRef,
      setPhase,
      setStreamedText,
      setChanges,
      setReasoning,
      setRequestId,
      setAcceptance,
      setErrorMsg,
    });
  }, [
    selectedFocus,
    chapterId,
    novelId,
    selectionText,
    contextBefore,
    contextAfter,
    t,
    setChanges,
    setAcceptance,
  ]);

  const handleApply = useCoAuthorApply({
    changes,
    acceptance,
    streamedText,
    requestId,
    chapterId,
    novelId,
    selectionText,
    onAccept,
    setPhase,
    setSubmitting,
    setErrorMsg,
    errorGeneric: t("coAuthor.errorGeneric"),
  });

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    onClose();
  }, [onClose]);

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setPhase(streamedText.trim().length > 0 ? "review" : "focus");
  }, [streamedText]);

  const handleRetry = useCallback(() => {
    setPhase("focus");
    setErrorMsg(null);
  }, []);

  const phaseLabel = getCoAuthorPhaseLabel(phase, t);

  return {
    phase,
    selectedFocus,
    streamedText,
    changes,
    reasoning,
    submitting,
    acceptance,
    errorMsg,
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
