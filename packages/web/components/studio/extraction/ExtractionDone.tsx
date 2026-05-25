"use client";

/**
 * ExtractionDone — Success state shown after extraction items
 * have been applied to the Knowledge Base.
 */

import { useTranslations } from "next-intl";

export function ExtractionDone() {
  const t = useTranslations("studio");

  return (
    <div className="text-center py-8">
      <p className="text-lg font-medium text-green-600 dark:text-green-400">
        {t("kb.extractionAppliedTitle")}
      </p>
      <p className="text-sm text-muted-foreground mt-2">{t("kb.extractionAppliedDesc")}</p>
    </div>
  );
}
