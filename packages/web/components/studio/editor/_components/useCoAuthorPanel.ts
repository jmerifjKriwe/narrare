"use client";

import { useTranslations } from "next-intl";
import { useCallback, useRef, useState } from "react";
import type { ChangeDetail, CoAuthorFocus } from "@/lib/api/coauthor";

import { applyPartialChanges } from "./coauthor-apply";
import {
  allChangesAccepted,
  createAcceptanceMap,
  getCoAuthorPhaseLabel,
} from "./coauthor-message-utils";
import { startCoAuthorStreaming } from "./coauthor-streaming";
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
  const [selectedFocus, setSelectedFocus] = useState<CoAuthorFocus[]>(["word_choice"]);
  const [streamedText, setStreamedText] = useState("");
  const [changes, setChanges] = useState<ChangeDetail[]>([]);
  const [reasoning, setReasoning] = useState("");
  const [requestId, setRequestId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [acceptance, setAcceptance] = useState<Record<string, boolean>>({});
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const toggleFocus = useCallback((value: CoAuthorFocus) => {
    setSelectedFocus((prev) => {
      if (prev.includes(value)) return prev.length <= 1 ? prev : prev.filter((f) => f !== value);
      return [...prev, value];
    });
  }, []);

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
  }, [selectedFocus, chapterId, novelId, selectionText, contextBefore, contextAfter, t]);

  const handleAcceptAll = useCallback(() => {
    setAcceptance(createAcceptanceMap(changes, true));
  }, [changes]);

  const handleRejectAll = useCallback(() => {
    setAcceptance(createAcceptanceMap(changes, false));
  }, [changes]);

  const handleToggleChange = useCallback((id: string) => {
    setAcceptance((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const handleApply = useCallback(async () => {
    if (allChangesAccepted(changes, acceptance)) {
      onAccept(streamedText);
      setPhase("done");
      return;
    }
    setSubmitting(true);
    try {
      const content = await applyPartialChanges({
        changes,
        acceptance,
        chapterId,
        novelId,
        requestId,
        selectionText,
      });
      onAccept(content);
      setPhase("done");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : t("coAuthor.errorGeneric"));
      setPhase("error");
    } finally {
      setSubmitting(false);
    }
  }, [
    acceptance,
    changes,
    chapterId,
    novelId,
    selectionText,
    streamedText,
    requestId,
    onAccept,
    t,
  ]);

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
