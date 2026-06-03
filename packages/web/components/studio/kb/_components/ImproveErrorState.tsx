"use client";

/**
 * Error state for the KB improve panel.
 *
 * Displays the error message with a retry button.
 */

import { RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";

interface ImproveErrorStateProps {
  error: Error;
  onRetry: () => void;
}

export function ImproveErrorState({ error, onRetry }: ImproveErrorStateProps) {
  const t = useTranslations("studio");

  return (
    <div className="p-4 border border-red-200 dark:border-red-900/50 rounded-lg bg-red-50 dark:bg-red-950/20">
      <div className="flex items-center justify-between">
        <p className="text-sm text-red-600 dark:text-red-400">
          {error.message || t("kb.improve.analysisError") || "Analysis failed"}
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-700"
        >
          <RotateCcw className="w-3 h-3" />
          {t("kb.retry") || "Retry"}
        </button>
      </div>
    </div>
  );
}
