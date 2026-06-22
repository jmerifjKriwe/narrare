"use client";

import { RotateCcw, Sparkles, X } from "lucide-react";
import { useEffect } from "react";

import {
  CoAuthorDonePhase,
  CoAuthorFocusSelector,
  CoAuthorReviewPhase,
  CoAuthorStreamingPhase,
} from "./_components";
import { btnPrimary, btnSecondary } from "./_components/coauthor-styles";
import { useCoAuthorPanel } from "./_components/useCoAuthorPanel";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type { CoAuthorPhase } from "./_components/coauthor-styles";

interface CoAuthorPanelProps {
  readonly novelId: string;
  readonly chapterId: string;
  readonly selectionText: string;
  readonly contextBefore?: string;
  readonly contextAfter?: string;
  readonly onAccept: (revisedText: string) => void;
  readonly onClose: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CoAuthorPanel({
  novelId,
  chapterId,
  selectionText,
  contextBefore,
  contextAfter,
  onAccept,
  onClose,
}: CoAuthorPanelProps) {
  const {
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
  } = useCoAuthorPanel({
    novelId,
    chapterId,
    selectionText,
    contextBefore,
    contextAfter,
    onAccept,
    onClose,
  });

  // Global Escape handler: cancel / close
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleCancel();
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [handleCancel]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card border border-border rounded-xl shadow-2xl max-w-lg w-full overflow-hidden">
        <div className="p-5 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary" />
            <h3 className="font-medium">{t("coAuthor.title")}</h3>
            {phaseLabel && <span className="text-xs text-muted-foreground ml-1">{phaseLabel}</span>}
          </div>
          <button
            type="button"
            onClick={handleCancel}
            className="p-1 rounded-md hover:bg-accent transition-colors"
            aria-label={t("coAuthor.close")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5">
          {phase === "focus" && (
            <CoAuthorFocusSelector
              selectedFocus={selectedFocus}
              onToggle={toggleFocus}
              selectionText={selectionText}
              onStart={handleStart}
            />
          )}
          {phase === "streaming" && (
            <CoAuthorStreamingPhase streamedText={streamedText} onStop={handleStop} />
          )}
          {phase === "review" && (
            <CoAuthorReviewPhase
              projectId={novelId}
              chapterId={chapterId}
              changes={changes}
              acceptance={acceptance}
              reasoning={reasoning}
              onToggleChange={handleToggleChange}
              onAcceptAll={handleAcceptAll}
              onRejectAll={handleRejectAll}
              onApply={handleApply}
              submitting={submitting}
              onClose={handleCancel}
            />
          )}
          {phase === "done" && <CoAuthorDonePhase onClose={onClose} />}
          {phase === "error" && (
            <div className="space-y-4">
              <div
                className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm"
                role="alert"
              >
                {errorMsg || t("coAuthor.errorGeneric")}
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleCancel}
                  className={`${btnSecondary} flex-1`}
                  data-testid="coauthor-error-close"
                >
                  {t("coAuthor.close")}
                </button>
                <button
                  type="button"
                  onClick={handleRetry}
                  className={`${btnPrimary} flex-1 flex items-center justify-center gap-2`}
                >
                  <RotateCcw className="w-4 h-4" />
                  <span>{t("aiActions.retry")}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
