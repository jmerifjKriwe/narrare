"use client";

import { AlertTriangle, Check, Loader2, Sparkles } from "lucide-react";
import type { useTranslations } from "next-intl";
import { useEffect } from "react";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { InlineDiff } from "./InlineDiff";
import { RewriteModalFooter } from "./RewriteModalFooter";
import type { AISuggestion } from "./TipTapEditorController";

type StudioTranslator = ReturnType<typeof useTranslations>;

interface RewriteSuggestionModalProps {
  aiSuggestion: AISuggestion;
  selectedSuggestion: number;
  onSelectedSuggestionChange: (index: number) => void;
  rejectionReason: string;
  onRejectionReasonChange: (reason: string) => void;
  showRejectionInput: boolean;
  isRewriteStreaming: boolean;
  rewriteError: AIErrorResponse | null;
  onReject: () => void;
  onInsertAsNew: () => void;
  onNewSuggestions: () => void;
  onAccept: () => void;
  t: StudioTranslator;
}

export function RewriteSuggestionModal({
  aiSuggestion,
  selectedSuggestion,
  onSelectedSuggestionChange,
  rejectionReason,
  onRejectionReasonChange,
  showRejectionInput,
  isRewriteStreaming,
  rewriteError,
  onReject,
  onInsertAsNew,
  onNewSuggestions,
  onAccept,
  t,
}: RewriteSuggestionModalProps) {
  // Keyboard Shortcuts Handler (KEYBOARD-001)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "y") {
        e.preventDefault();
        onAccept();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "n") {
        e.preventDefault();
        onReject();
      }
      if (e.key === "Escape" && isRewriteStreaming) {
        e.preventDefault();
        onNewSuggestions(); // Retry = neue Vorschläge laden
      }
      if (e.key === "Escape" && !isRewriteStreaming) {
        e.preventDefault();
        onReject(); // Modal schließen bei nicht-streaming
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isRewriteStreaming, onAccept, onReject, onNewSuggestions]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card border border-border rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col">
        <div className="p-6 border-b border-border">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-5 h-5 text-primary" />
            <h3 className="font-medium">{t("aiModal.title")}</h3>
          </div>
          <p className="text-sm text-muted-foreground">
            {t("aiModal.original", { text: aiSuggestion.original })}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <div className="space-y-3">
            {aiSuggestion.suggestions.map((suggestion, index) => (
              <button
                type="button"
                key={`suggestion-${suggestion.slice(0, 32)}`}
                onClick={() => onSelectedSuggestionChange(index)}
                className={`w-full text-left p-4 rounded-lg border-2 transition-all ${selectedSuggestion === index ? "border-primary bg-accent" : "border-border hover:border-primary/50"}`}
              >
                {aiSuggestion.labels[index] && (
                  <p className="text-xs font-medium text-muted-foreground mb-2">
                    {aiSuggestion.labels[index]}
                  </p>
                )}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <InlineDiff original={aiSuggestion.original} alternative={suggestion} />
                  </div>
                  {selectedSuggestion === index && (
                    <Check className="w-5 h-5 text-primary flex-shrink-0" />
                  )}
                </div>
              </button>
            ))}
          </div>
          {isRewriteStreaming && (
            <div className="flex items-center gap-2 mt-4 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>{t("aiActions.generating")}</span>
            </div>
          )}

          {/* Structured error display (§11 no silent failures) */}
          {rewriteError && !isRewriteStreaming && (
            <div className="flex items-start gap-2 mt-4 p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-lg text-sm">
              <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-red-700 dark:text-red-400 font-medium">
                  {getErrorMessage(rewriteError, t)}
                </p>
                {rewriteError.retryable && (
                  <button
                    type="button"
                    onClick={onNewSuggestions}
                    className="mt-1 text-red-600 dark:text-red-400 underline hover:no-underline"
                  >
                    {t("aiActions.retry")}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {showRejectionInput && (
          <div className="p-6 border-t border-border bg-muted/30">
            <label htmlFor="rejection-reason" className="block text-sm mb-2">
              {t("aiActions.rejectReason")}
            </label>
            <textarea
              id="rejection-reason"
              value={rejectionReason}
              onChange={(event) => onRejectionReasonChange(event.target.value)}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-lg text-sm"
              rows={3}
              placeholder={t("aiActions.rejectReasonPlaceholder")}
            />
          </div>
        )}

        <RewriteModalFooter
          onReject={onReject}
          onInsertAsNew={onInsertAsNew}
          onNewSuggestions={onNewSuggestions}
          onAccept={onAccept}
          t={t}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Resolve a structured AIErrorResponse to a user-facing message.
 * Uses the i18n key when available, falls back to the mapped userMessage.
 */
function getErrorMessage(error: AIErrorResponse, t: StudioTranslator): string {
  try {
    return t(error.i18nKey as Parameters<typeof t>[0]);
  } catch {
    return error.userMessage || t("aiActions.errorDefault");
  }
}
