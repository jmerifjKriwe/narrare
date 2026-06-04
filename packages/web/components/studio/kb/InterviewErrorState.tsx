"use client";

/**
 * InterviewErrorState — Error display with retry button for interview mode.
 *
 * Extracted from KBInterviewView for RULE-04 compliance.
 */

import { useTranslations } from "next-intl";

interface InterviewErrorStateProps {
  error: Error;
  onRetry: () => void;
}

export function InterviewErrorState({ error, onRetry }: InterviewErrorStateProps) {
  const t = useTranslations("studio");

  return (
    <div className="p-4 border border-red-200 dark:border-red-900/50 rounded-lg bg-red-50 dark:bg-red-950/20">
      <div className="flex items-center justify-between">
        <p className="text-sm text-red-600 dark:text-red-400">
          {error.message || "Failed to get question"}
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-700"
        >
          {t("kb.retry") || "Retry"}
        </button>
      </div>
    </div>
  );
}
