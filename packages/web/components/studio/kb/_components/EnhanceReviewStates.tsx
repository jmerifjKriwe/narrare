import { Loader2, OctagonX, RotateCcw } from "lucide-react";

import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";

interface EnhanceLoadingStateProps {
  t: (key: string) => string;
  /** If provided, shows a cancel/stop button. */
  onCancel?: () => void;
}

interface EnhanceErrorStateProps {
  error: AIErrorResponse;
  onRetry: () => void;
  t: (key: string) => string;
}

export function EnhanceLoadingState({ t, onCancel }: EnhanceLoadingStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="relative mb-6">
        <div className="w-16 h-16 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
        </div>
      </div>
      <p className="text-lg font-medium mb-2">{t("aiActions.generating")}</p>
      <p className="text-sm text-muted-foreground">{t("kb.aiEnhancingDesc")}</p>
      <div className="w-64 h-1.5 bg-muted rounded-full overflow-hidden mt-6">
        <div className="h-full bg-purple-500 animate-pulse w-3/5" />
      </div>
      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="flex items-center gap-1.5 mt-6 px-4 py-2 text-sm text-muted-foreground hover:text-foreground border border-border rounded-md hover:bg-muted transition-colors"
        >
          <OctagonX className="w-4 h-4" />
          {t("aiActions.stop")}
        </button>
      )}
    </div>
  );
}

export function EnhanceErrorState({ error, onRetry, t }: EnhanceErrorStateProps) {
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
