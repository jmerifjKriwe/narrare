"use client";

/**
 * Loading state for the KB improve panel.
 *
 * Displays a spinner and progress indicator during analysis.
 * When onCancel is provided, shows a visible cancel control (§16.2).
 */

import { Loader2, OctagonX } from "lucide-react";
import { useTranslations } from "next-intl";

interface ImproveLoadingStateProps {
  /** If provided, shows a cancel/stop button (§16.2 cancel_ui). */
  onCancel?: () => void;
}

export function ImproveLoadingState({ onCancel }: ImproveLoadingStateProps = {}) {
  const t = useTranslations("studio");

  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="relative mb-6">
        <div className="w-16 h-16 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
        </div>
      </div>
      <p className="text-lg font-medium mb-2">{t("kb.improve.running")}</p>
      <p className="text-sm text-muted-foreground">{t("kb.aiEnhancingDesc")}</p>
      {/* Progress indicator */}
      <div className="w-64 h-1.5 bg-muted rounded-full overflow-hidden mt-6">
        <div className="h-full bg-purple-500 animate-pulse" style={{ width: "60%" }} />
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
