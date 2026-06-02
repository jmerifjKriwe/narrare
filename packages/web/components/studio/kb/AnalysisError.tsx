"use client";

/**
 * AnalysisError — Error state for worldbuilding analysis.
 *
 * Actionable error message (§16.5) with retry using studio.aiActions.retry.
 */

import { AlertTriangle, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";

interface AnalysisErrorProps {
  readonly message: string;
  readonly onRetry: () => void;
}

export function AnalysisError({ message, onRetry }: AnalysisErrorProps) {
  const t = useTranslations("studio");
  const tAction = useTranslations("studio.aiActions");

  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
        <AlertTriangle className="w-6 h-6 text-red-500" />
      </div>
      <p className="text-lg font-medium mb-1">{t("worldbuilding.error") || "Analysis failed"}</p>
      <p className="text-sm text-muted-foreground mb-4">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
      >
        <RefreshCw className="w-4 h-4" />
        {tAction("retry")}
      </button>
    </div>
  );
}
