"use client";

import { useLocale, useTranslations } from "next-intl";
import type { ModelCatalogProvenance } from "@/types";

/**
 * Format an ISO date (`YYYY-MM-DD`) as a locale-aware "Month Year" string.
 * Constructed from parts in local time so the day never shifts across
 * timezones. Falls back to the raw string if it cannot be parsed.
 */
function formatReviewedDate(isoDate: string, locale: string): string {
  const parts = isoDate.split("-").map(Number);
  const [year, month, day] = parts;
  if (!year || !month || !day || parts.some((n) => Number.isNaN(n))) {
    return isoDate;
  }
  return new Intl.DateTimeFormat(locale, { year: "numeric", month: "long" }).format(
    new Date(year, month - 1, day),
  );
}

interface FallbackCatalogNoticeProps {
  /**
   * Catalog provenance from the last model-list fetch. The notice only
   * renders when `source === "bundled-fallback"` (offline static list);
   * otherwise the component returns `null`.
   */
  provenance: ModelCatalogProvenance | null;
}

/**
 * Offline fallback notice for the model catalog. Shown only when the
 * provider model list was served from the bundled static fallback rather
 * than fetched live, flagging it as potentially stale.
 */
export function FallbackCatalogNotice({ provenance }: FallbackCatalogNoticeProps) {
  const t = useTranslations("studio");
  const locale = useLocale();

  if (provenance?.source !== "bundled-fallback") {
    return null;
  }

  return (
    <p
      data-testid="fallback-catalog-notice"
      className="text-xs text-muted-foreground bg-muted/50 border border-border rounded-md p-2 leading-relaxed"
    >
      {t("wizard.step4.fallbackCatalogNotice")}
      {provenance.last_reviewed && (
        <span data-testid="fallback-reviewed-date" className="block mt-1">
          {t("wizard.step4.fallbackCatalogReviewed")}{" "}
          {formatReviewedDate(provenance.last_reviewed, locale)}
        </span>
      )}
    </p>
  );
}
