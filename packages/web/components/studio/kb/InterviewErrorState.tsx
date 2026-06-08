"use client";

/**
 * InterviewErrorState — Error display with retry button for interview mode.
 *
 * Extracted from KBInterviewView for RULE-04 compliance.
 * Uses structured AIErrorResponse from useAIOperation (§16).
 */

import { RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";

import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";

interface InterviewErrorStateProps {
  error: AIErrorResponse;
  onRetry: () => void;
}

export function InterviewErrorState({ error, onRetry }: InterviewErrorStateProps) {
  const t = useTranslations("studio");
  const displayMessage = error.i18nKey ? t(error.i18nKey) : error.userMessage;

  return (
    <div className="p-4 border border-red-200 dark:border-red-900/50 rounded-lg bg-red-50 dark:bg-red-950/20">
      <div className="flex items-center justify-between">
        <p className="text-sm text-red-600 dark:text-red-400">{displayMessage}</p>
        {error.retryable && (
          <button
            type="button"
            onClick={onRetry}
            className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-700"
          >
            <RotateCcw className="w-3 h-3" />
            {t("aiActions.retry")}
          </button>
        )}
      </div>
    </div>
  );
}
