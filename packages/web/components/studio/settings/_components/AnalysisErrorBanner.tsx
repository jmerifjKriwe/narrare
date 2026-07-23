"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AnalysisErrorBannerProps {
  /** Mapped analysis error, or null when there is no error (renders nothing). */
  readonly analysisError: AIErrorResponse | null;
  /** Whether the failure is a network/connection-lost error (§16.4). */
  readonly isConnectionLost: boolean;
  /** Whether a retry is currently in-flight (disables the retry button). */
  readonly isPending: boolean;
  /** Retry handler — re-triggers the analysis. */
  readonly onRetry: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Analysis error banner — mapped message + retry, with connection-lost styling
 * when the failure is a network error (§16.4 parity with GenerationPanel).
 *
 * Renders nothing when {@link AnalysisErrorBannerProps.analysisError} is null.
 */
export function AnalysisErrorBanner({
  analysisError,
  isConnectionLost,
  isPending,
  onRetry,
}: AnalysisErrorBannerProps) {
  const t = useTranslations("studio");

  if (!analysisError) {
    return null;
  }

  return (
    <div
      className={
        isConnectionLost
          ? "flex items-center justify-between gap-3 p-3 rounded-lg bg-yellow-500/10"
          : "flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm"
      }
      role="alert"
    >
      <div
        className={
          isConnectionLost
            ? "flex items-center gap-2 text-sm text-yellow-700 dark:text-yellow-400"
            : "flex items-center gap-2"
        }
      >
        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
        <span>{analysisError.userMessage}</span>
      </div>
      <button
        type="button"
        onClick={onRetry}
        disabled={isPending}
        className={
          isConnectionLost
            ? "flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-md bg-yellow-600 text-white hover:bg-yellow-700 transition-colors disabled:opacity-50"
            : "flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-md border border-border text-foreground hover:bg-accent transition-colors disabled:opacity-50"
        }
      >
        <RotateCcw className="w-3.5 h-3.5" />
        <span>{isConnectionLost ? t("aiActions.connectionLostRetry") : t("aiActions.retry")}</span>
      </button>
    </div>
  );
}
