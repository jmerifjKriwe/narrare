"use client";

/**
 * ExtractionPanel — Main orchestration container for KB extraction.
 *
 * Phase state machine: loading → review → applying → done | error
 * On mount: triggers extractChapter mutation.
 * On apply: calls applyExtraction with selected items.
 * On success: calls onApplied, auto-closes after 2s.
 *
 * §16 compliance: AbortController cancel, useConnectionLost,
 * studio.aiActions.* labels, actionable error messages.
 */

import { Database, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { ConnectionLostBanner } from "@/components/ui/connection-lost-banner";
import type { ApplyExtractionItem } from "@/lib/api/extraction";
import { useConnectionLost } from "@/lib/hooks/use-connection-lost";
import { useApplyExtraction, useExtractChapter } from "@/lib/hooks/useExtraction";
import { useExtractionSelection } from "@/lib/hooks/useExtractionSelection";
import { ExtractionContent } from "./ExtractionContent";
import { ExtractionFooter } from "./ExtractionFooter";

type ExtractionPhase = "loading" | "review" | "applying" | "done" | "error";

interface ExtractionPanelProps {
  novelId: string;
  chapterId: string;
  onClose: () => void;
  onApplied: () => void;
}

/** Extract user-visible message from an error, preferring structured AIErrorResponse. */
function getErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error && "userMessage" in err) {
    return (err as { userMessage: string }).userMessage;
  }
  return err instanceof Error ? err["message"] : fallback;
}

export function ExtractionPanel({ novelId, chapterId, onClose, onApplied }: ExtractionPanelProps) {
  const t = useTranslations("studio");
  const [phase, setPhase] = useState<ExtractionPhase>("loading");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const autoCloseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const extractMutation = useExtractChapter(novelId, chapterId);
  const applyMutation = useApplyExtraction(novelId);
  const selection = useExtractionSelection();

  const {
    isConnectionLost,
    markConnectionLost,
    retry: retryConnection,
  } = useConnectionLost({
    onRetry: () => handleRetry(),
  });

  // Check for abort errors (user cancelled — not a real error)
  const isAbortError = useCallback((err: unknown) => {
    return err instanceof DOMException && err.name === "AbortError";
  }, []);

  const onError = useCallback(
    (err: unknown) => {
      if (isAbortError(err)) {
        // User cancelled — return to review or close, not error state
        if (phase === "loading") onClose();
        return;
      }
      markConnectionLost();
      setErrorMsg(getErrorMessage(err, t("kb.extractionFailed")));
      setPhase("error");
    },
    [t, markConnectionLost, isAbortError, phase, onClose],
  );

  // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only trigger
  useEffect(() => {
    extractMutation.mutate(undefined, {
      onSuccess: (output) => {
        selection.loadResults(output);
        setPhase("review");
      },
      onError,
    });
  }, [selection.loadResults, onError, extractMutation.mutate]);

  useEffect(() => {
    if (phase === "done") autoCloseTimer.current = setTimeout(onClose, 2000);
    return () => {
      if (autoCloseTimer.current) clearTimeout(autoCloseTimer.current);
    };
  }, [phase, onClose]);

  const handleApply = useCallback(() => {
    const selected: ApplyExtractionItem[] = selection.items
      .filter((_, idx) => selection.selectedIndices.has(idx))
      .map((item) => ({
        item_type: item.item_type,
        name: item.name,
        entity_type: item.entity_type,
        proposed_content: item.proposed_content,
        target_entity_id: item.target_entity_id,
        relationship_type: item.relationship_type,
        related_entity_name: item.related_entity_name,
        source_text: item.source_text,
      }));
    setPhase("applying");
    applyMutation.mutate(selected, {
      onSuccess: () => {
        setPhase("done");
        onApplied();
      },
      onError: (err) => {
        if (isAbortError(err)) return;
        setErrorMsg(getErrorMessage(err, t("kb.extractionApplyError")));
        setPhase("error");
      },
    });
  }, [selection, applyMutation, onApplied, t, isAbortError]);

  const handleRetry = useCallback(() => {
    setErrorMsg(null);
    setPhase("loading");
    extractMutation.mutate(undefined, {
      onSuccess: (output) => {
        selection.loadResults(output);
        setPhase("review");
      },
      onError,
    });
  }, [extractMutation, selection, onError]);

  const handleCancelExtraction = useCallback(() => {
    extractMutation.abort();
    onClose();
  }, [extractMutation, onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-border bg-card">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-primary" />
            <h3 className="font-medium">
              {phase === "done" ? t("kb.extractionComplete") : t("kb.extractionLoadingTitle")}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-accent transition-colors"
            aria-label={t("kb.extractionCancel")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        {isConnectionLost && (
          <div className="px-4 pt-4">
            <ConnectionLostBanner onRetry={retryConnection} />
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto">
            <ExtractionContent
              phase={phase}
              items={selection.items}
              selectedIndices={selection.selectedIndices}
              analysisNotes={selection.analysisNotes}
              errorMsg={errorMsg}
              onToggleItem={selection.toggleItem}
              onSelectAll={selection.selectAll}
              onSelectNone={selection.selectNone}
              onRetry={handleRetry}
              onCancel={phase === "loading" ? handleCancelExtraction : undefined}
            />
          </div>
        </div>
        {(phase === "review" || phase === "applying") && (
          <ExtractionFooter
            selectedCount={selection.selectedIndices.size}
            totalCount={selection.items.length}
            isApplying={phase === "applying"}
            onCancel={onClose}
            onApply={handleApply}
          />
        )}
      </div>
    </div>
  );
}
