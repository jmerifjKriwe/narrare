"use client";

/**
 * ExtractionError — Error state with retry button.
 *
 * Follows KBEnhanceReview error pattern.
 */

import { RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";

interface ExtractionErrorProps {
  message: string;
  onRetry: () => void;
}

export function ExtractionError({ message, onRetry }: ExtractionErrorProps) {
  const t = useTranslations("studio");

  return (
    <div className="p-4 border border-red-200 dark:border-red-900/50 rounded-lg bg-red-50 dark:bg-red-950/20">
      <div className="flex items-center justify-between">
        <p className="text-sm text-red-600 dark:text-red-400">{message}</p>
        <button
          type="button"
          onClick={onRetry}
          className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-700"
        >
          <RotateCcw className="w-3 h-3" />
          {t("kb.extractionRetry")}
        </button>
      </div>
    </div>
  );
}
