import { Loader2, RotateCcw } from "lucide-react";

interface EnhanceLoadingStateProps {
  t: (key: string) => string;
}

interface EnhanceErrorStateProps {
  error: Error;
  onRetry: () => void;
  t: (key: string) => string;
}

export function EnhanceLoadingState({ t }: EnhanceLoadingStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="relative mb-6">
        <div className="w-16 h-16 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
        </div>
      </div>
      <p className="text-lg font-medium mb-2">{t("kb.aiEnhancing")}</p>
      <p className="text-sm text-muted-foreground">
        {t("kb.aiEnhancingDesc") || "The AI is reviewing and enhancing your entry..."}
      </p>
      <div className="w-64 h-1.5 bg-muted rounded-full overflow-hidden mt-6">
        <div className="h-full bg-purple-500 animate-pulse w-3/5" />
      </div>
    </div>
  );
}

export function EnhanceErrorState({ error, onRetry, t }: EnhanceErrorStateProps) {
  return (
    <div className="p-4 border border-red-200 dark:border-red-900/50 rounded-lg bg-red-50 dark:bg-red-950/20">
      <div className="flex items-center justify-between">
        <p className="text-sm text-red-600 dark:text-red-400">
          {error.message || "Enhancement failed"}
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
