"use client";

/**
 * useExtractionPhase — Phase state machine for KB extraction.
 *
 * Manages the loading → review → applying → done | error lifecycle.
 * On mount: triggers extractChapter mutation.
 * On apply: calls applyExtraction with selected items.
 * On success: auto-closes after 2s (via useExtractionAutoClose).
 *
 * §16 compliance: All AI operations run through useAIOperation via
 * useExtractChapter/useApplyExtraction. No raw AbortController or
 * deprecated useConnectionLost. Connection-loss state and retry come
 * directly from the useAIOperation-backed mutation hooks.
 */

import type { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { useApplyExtraction, useExtractChapter } from "@/lib/hooks/useExtraction";
import { useExtractionSelection } from "@/lib/hooks/useExtractionSelection";
import {
  type ExtractionPhase,
  getErrorMessage,
  handleExtractionError,
  isAbortError,
  mapSelectedItems,
} from "./extraction-utils";
import { useExtractionAutoClose } from "./useExtractionAutoClose";

export type { ExtractionPhase };

/** Translation function type matching the project convention. */
type StudioTranslator = ReturnType<typeof useTranslations>;

export interface UseExtractionPhaseParams {
  novelId: string;
  chapterId: string;
  onClose: () => void;
  onApplied: () => void;
  /** Translation function for the "studio" namespace. */
  t: StudioTranslator;
}

export function useExtractionPhase({
  novelId,
  chapterId,
  onClose,
  onApplied,
  t,
}: UseExtractionPhaseParams) {
  const [phase, setPhase] = useState<ExtractionPhase>("loading");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // AI operation mutations — both backed by useAIOperation (§16).
  // isConnectionLost and retry come from the extract mutation.
  const extractMutation = useExtractChapter(novelId, chapterId);
  const applyMutation = useApplyExtraction(novelId);
  const selection = useExtractionSelection();

  // Auto-close on "done" phase after a short delay.
  useExtractionAutoClose(phase, "done", onClose);

  // Mount-only trigger: extract on open. M01: startedRef makes this true
  // even though the effect's deps include `extractMutation.mutateAsync`,
  // whose identity changes on every useAIOperation state transition —
  // without the guard each transition re-fired POST /kb/extract/{chapter}
  // (audit: 697 calls in one modal session). Retry stays explicit
  // (handleRetry below). Deliberately NO cancelled-cleanup: under dev
  // StrictMode (setup → cleanup → setup) cancelling the first run while
  // the guard skips the second would drop the only in-flight extraction;
  // same fire-once shape as CharacterVoicePanel/useBulkExtractionController.
  const startedRef = useRef(false);
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    extractMutation
      .mutateAsync()
      .then((output) => {
        selection.loadResults(output);
        setPhase("review");
      })
      .catch((err) => {
        handleExtractionError(err, t("kb.extractionFailed"), {
          onClose,
          setErrorMsg,
          setPhase,
        });
      });
  }, [extractMutation.mutateAsync, t, selection.loadResults, onClose]);

  const handleApply = useCallback(() => {
    const selected = mapSelectedItems(selection.items, selection.selectedIndices);
    setPhase("applying");

    applyMutation
      .mutateAsync(selected)
      .then(() => {
        setPhase("done");
        onApplied();
      })
      .catch((err) => {
        if (isAbortError(err)) return;
        setErrorMsg(getErrorMessage(err, t("kb.extractionApplyError")));
        setPhase("error");
      });
  }, [selection, applyMutation, onApplied, t]);

  const handleRetry = useCallback(() => {
    setErrorMsg(null);
    setPhase("loading");

    extractMutation
      .mutateAsync()
      .then((output) => {
        selection.loadResults(output);
        setPhase("review");
      })
      .catch((err) => {
        handleExtractionError(err, t("kb.extractionFailed"), {
          onClose,
          setErrorMsg,
          setPhase,
        });
      });
  }, [extractMutation, selection, onClose, t]);

  const handleCancelExtraction = useCallback(() => {
    extractMutation.abort();
    onClose();
  }, [extractMutation, onClose]);

  return {
    phase,
    errorMsg,
    isConnectionLost: extractMutation.isConnectionLost,
    selectedItems: selection.items,
    selectedIndices: selection.selectedIndices,
    analysisNotes: selection.analysisNotes,
    handleApply,
    handleRetry,
    handleCancelExtraction,
    retryConnection: extractMutation.retry,
    // Selection actions forwarded for the UI
    toggleItem: selection.toggleItem,
    selectAll: selection.selectAll,
    selectNone: selection.selectNone,
  };
}
