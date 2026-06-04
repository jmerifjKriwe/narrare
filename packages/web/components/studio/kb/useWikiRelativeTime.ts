/**
 * useWikiRelativeTime — Computes a localized relative time string for wiki panels.
 *
 * Shared between WikiOverviewPanel and WikiChapterSummaryPanel.
 */

import { useTranslations } from "next-intl";
import { useMemo } from "react";

export function useWikiRelativeTime(dateStr: string | null | undefined): string | null {
  const t = useTranslations("studio");

  return useMemo(() => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) return t("kb.wiki.justNow");
    if (diffMinutes < 60) return t("kb.wiki.minutesAgo", { count: diffMinutes });
    if (diffHours < 24) return t("kb.wiki.hoursAgo", { count: diffHours });
    return t("kb.wiki.daysAgo", { count: diffDays });
  }, [dateStr, t]);
}
