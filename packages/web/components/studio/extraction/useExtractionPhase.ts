"use client";

/**
 * useExtractionPhase — Phase state machine for KB extraction.
 *
 * Manages the loading → review → applying → done | error lifecycle.
 * On mount: triggers extractChapter mutation.
 * On apply: calls applyExtraction with selected items.
 * On success: calls onApplied, auto-closes after 2s.
 *
 * §16 compliance: AbortController cancel, useConnectionLost,
 * actionable error messages.
 */

import type { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { useConnectionLost } from "@/lib/hooks/use-connection-lost";
import { useApplyExtraction, useExtractChapter } from "@/lib/hooks/useExtraction";
import { useExtractionSelection } from "@/lib/hooks/useExtractionSelection";
import {
  type ExtractionPhase,
  getErrorMessage,
  handleExtractionError,
  isAbortError,
  mapSelectedItems,
} from "./extraction-utils";

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
  const autoCloseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const extractMutation = useExtractChapter(novelId, chapterId);
  const applyMutation = useApplyExtraction(novelId);
  const selection = useExtractionSelection();

  // Connection lost detection. The onRetry closure captures handleRetry by reference —
  // safe because handleRetry is defined before onRetry is ever invoked.
  const {
    isConnectionLost,
    markConnectionLost,
    retry: retryConnection,
  } = useConnectionLost({
    onRetry: () => handleRetry(),
  });

  // Mount-only trigger: extract on open.
  useEffect(() => {
    let cancelled = false;

    extractMutation
      .mutateAsync()
      .then((output) => {
        if (cancelled) return;
        selection.loadResults(output);
        setPhase("review");
      })
      .catch((err) => {
        if (cancelled) return;
        handleExtractionError(err, t("kb.extractionFailed"), {
          onClose,
          markConnectionLost,
          setErrorMsg,
          setPhase,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [extractMutation.mutateAsync, markConnectionLost, t, selection.loadResults, onClose]);

  // Auto-close after successful apply
  useEffect(() => {
    if (phase === "done") autoCloseTimer.current = setTimeout(onClose, 2000);
    return () => {
      if (autoCloseTimer.current) clearTimeout(autoCloseTimer.current);
    };
  }, [phase, onClose]);

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
          markConnectionLost,
          setErrorMsg,
          setPhase,
        });
      });
  }, [extractMutation, selection, onClose, t, markConnectionLost]);

  const handleCancelExtraction = useCallback(() => {
    extractMutation.abort();
    onClose();
  }, [extractMutation, onClose]);

  return {
    phase,
    errorMsg,
    isConnectionLost,
    selectedItems: selection.items,
    selectedIndices: selection.selectedIndices,
    analysisNotes: selection.analysisNotes,
    handleApply,
    handleRetry,
    handleCancelExtraction,
    retryConnection,
    // Selection actions forwarded for the UI
    toggleItem: selection.toggleItem,
    selectAll: selection.selectAll,
    selectNone: selection.selectNone,
  };
}
