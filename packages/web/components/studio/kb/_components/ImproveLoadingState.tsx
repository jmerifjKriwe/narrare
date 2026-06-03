"use client";

/**
 * Loading state for the KB improve panel.
 *
 * Displays a spinner and progress indicator during analysis.
 */

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";

export function ImproveLoadingState() {
  const t = useTranslations("studio");

  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="relative mb-6">
        <div className="w-16 h-16 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
        </div>
      </div>
      <p className="text-lg font-medium mb-2">{t("kb.improve.running") || "Analyzing entry..."}</p>
      <p className="text-sm text-muted-foreground">
        {t("kb.aiEnhancingDesc") || "The AI is reviewing and enhancing your entry..."}
      </p>
      {/* Progress indicator */}
      <div className="w-64 h-1.5 bg-muted rounded-full overflow-hidden mt-6">
        <div className="h-full bg-purple-500 animate-pulse" style={{ width: "60%" }} />
      </div>
    </div>
  );
}
