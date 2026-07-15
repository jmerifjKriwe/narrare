"use client";

/**
 * InterviewLoadingState — transient AI-operation status for the KB Interview.
 *
 * Renders the two transient overlays that surface while an AI operation is in
 * flight: the loading spinner (with a cancel affordance) and the
 * connection-lost banner (with retry). Both are driven by the
 * useAIOperation lifecycle (§16) and are mutually exclusive with the
 * InterviewErrorState block in the parent.
 *
 * Extracted from KBInterviewView for RULE-04 file-size compliance.
 */

import { Loader2, OctagonX } from "lucide-react";
import { useTranslations } from "next-intl";

interface InterviewLoadingStateProps {
  /** True while the AI operation is actively loading/streaming. */
  readonly isLoading: boolean;
  /** True when the connection was lost and a retry is available. */
  readonly isConnectionLost: boolean;
  /** Cancel the in-progress AI operation. */
  readonly onCancel: () => void;
  /** Retry the AI operation after a connection loss. */
  readonly onRetry: () => void;
}

export function InterviewLoadingState({
  isLoading,
  isConnectionLost,
  onCancel,
  onRetry,
}: InterviewLoadingStateProps) {
  const t = useTranslations("studio");

  return (
    <>
      {/* Loading state */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Loader2 className="w-8 h-8 text-muted-foreground animate-spin mb-4" />
          <p className="text-muted-foreground">{t("aiActions.aiThinking")}</p>
          <button
            type="button"
            onClick={onCancel}
            className="flex items-center gap-1.5 mt-4 px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground border border-border rounded-md hover:bg-muted transition-colors"
          >
            <OctagonX className="w-3.5 h-3.5" />
            {t("aiActions.stop")}
          </button>
        </div>
      )}

      {/* Connection lost state */}
      {isConnectionLost && (
        <div className="p-4 border border-amber-200 dark:border-amber-900/50 rounded-lg bg-amber-50 dark:bg-amber-950/20">
          <div className="flex items-center justify-between">
            <p className="text-sm text-amber-600 dark:text-amber-400">
              {t("aiActions.connectionLost")}
            </p>
            <button
              type="button"
              onClick={onRetry}
              className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 hover:text-amber-700"
            >
              {t("aiActions.connectionLostRetry")}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
