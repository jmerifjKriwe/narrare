"use client";

/**
 * ExtractionDone — Success state shown after extraction items
 * have been applied to the Knowledge Base.
 *
 * The accessible `role="status"` / polite live region and standardised
 * styling are provided by the `StatusMessage` primitive; the secondary
 * description is rendered as a sibling so both i18n strings remain
 * addressable.
 */

import { useTranslations } from "next-intl";
import { StatusMessage } from "@/components/ui/status-message";

export function ExtractionDone() {
  const t = useTranslations("studio");

  return (
    <div className="py-8 text-center">
      <StatusMessage state="success" message={t("kb.extractionAppliedTitle")} />
      <p className="mt-2 text-sm text-muted-foreground">{t("kb.extractionAppliedDesc")}</p>
    </div>
  );
}
