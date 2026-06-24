"use client";

/**
 * PromptHistoryStatus — loading / error / empty states for the revision list
 * (CR-AUFG-07-19).
 *
 * Presentational: split out of :component:`PromptHistoryPanel` for RULE-04.
 * Renders exactly one status block based on the ``status`` prop. The caller
 * keeps the "ready" branch (list + compare) inline because it composes other
 * components rather than rendering a status block.
 */
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";

export type PromptHistoryStatusKind = "loading" | "error" | "empty";

interface PromptHistoryStatusProps {
  readonly status: PromptHistoryStatusKind;
  /** Only used by the "error" status. */
  readonly onRetry?: () => void;
}

export function PromptHistoryStatus({ status, onRetry }: PromptHistoryStatusProps) {
  const t = useTranslations("studio");
  const k = "settings.prompts.promptHistory";

  if (status === "loading") {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground" role="status">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t(`${k}.loading`)}
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="space-y-2">
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">
          {t(`${k}.loadFailed`)}
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md bg-muted px-3 py-1.5 text-xs hover:bg-accent transition-colors"
        >
          {t(`${k}.retry`)}
        </button>
      </div>
    );
  }

  // empty
  return (
    <div className="space-y-1 py-2 text-sm">
      <p className="font-medium text-foreground">{t(`${k}.empty`)}</p>
      <p className="text-xs text-muted-foreground">{t(`${k}.emptyHint`)}</p>
    </div>
  );
}
