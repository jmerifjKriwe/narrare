"use client";

/**
 * WikiIndexStats — Stats panel showing wiki summary counts by status.
 *
 * Extracted from WikiOverviewPanel for RULE-04 compliance.
 */

import { useTranslations } from "next-intl";
import type { WikiIndexResponse } from "@/lib/api/wiki";
import { WikiStatusDot } from "./WikiStatusDot";

interface WikiIndexStatsProps {
  indexData: WikiIndexResponse | undefined;
  relativeTime: string | null;
}

export function WikiIndexStats({ indexData, relativeTime }: WikiIndexStatsProps) {
  const t = useTranslations("studio");
  const staleCount = indexData?.stale_count ?? 0;
  const pendingCount = indexData?.pending_count ?? 0;

  return (
    <div className="border border-border/50 rounded-lg p-4 space-y-2">
      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
        {t("kb.wiki.indexStats")}
      </h3>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <span className="flex items-center gap-1.5">
          <WikiStatusDot status="fresh" size="sm" />
          {t("kb.wiki.fresh")}: {indexData?.fresh_count ?? 0}
        </span>
        <span className="flex items-center gap-1.5">
          <WikiStatusDot status="stale" size="sm" />
          {t("kb.wiki.stale")}: {staleCount}
        </span>
        <span className="flex items-center gap-1.5">
          <WikiStatusDot status="pending" size="sm" />
          {t("kb.wiki.pending")}: {pendingCount}
        </span>
        <span className="text-muted-foreground">
          {t("kb.wiki.total")}: {indexData?.total_summaries ?? 0}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        {relativeTime
          ? `${t("kb.wiki.lastGenerated")}: ${relativeTime}`
          : t("kb.wiki.neverGenerated")}
      </p>
    </div>
  );
}
