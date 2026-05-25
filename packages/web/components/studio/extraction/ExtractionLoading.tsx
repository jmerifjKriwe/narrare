"use client";

/**
 * ExtractionLoading — Loading state shown while the extraction agent
 * analyzes the chapter text.
 *
 * Spinner + i18n title/description. Matches KBEnhanceReview loading pattern.
 */

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";

export function ExtractionLoading() {
  const t = useTranslations("studio");

  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="relative mb-6">
        <div className="w-16 h-16 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
        </div>
      </div>
      <p className="text-lg font-medium mb-2">{t("kb.extractionLoadingTitle")}</p>
      <p className="text-sm text-muted-foreground max-w-sm">{t("kb.extractionLoadingDesc")}</p>
      <div className="w-64 h-1.5 bg-muted rounded-full overflow-hidden mt-6">
        <div className="h-full bg-purple-500 animate-pulse" style={{ width: "60%" }} />
      </div>
    </div>
  );
}
