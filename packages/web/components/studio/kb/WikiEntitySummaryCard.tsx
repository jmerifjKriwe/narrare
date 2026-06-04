"use client";

/**
 * WikiEntitySummaryCard — Card displaying a single entity's wiki summary with refresh action.
 *
 * Extracted from WikiOverviewPanel for RULE-04 compliance.
 */

import { Loader2, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import type { WikiSummaryResponse } from "@/lib/api/wiki";
import type { useWikiRefresh } from "@/lib/hooks/useWiki";
import { WikiStatusDot } from "./WikiStatusDot";

interface WikiEntitySummaryCardProps {
  summary: WikiSummaryResponse;
  refreshMutation: ReturnType<typeof useWikiRefresh>;
}

export function WikiEntitySummaryCard({ summary, refreshMutation }: WikiEntitySummaryCardProps) {
  const t = useTranslations("studio");
  const isRefreshing = refreshMutation.isPending;
  const entityName = summary.entity_id;
  const label = summary.narrative_summary
    ? summary.narrative_summary.length > 120
      ? `${summary.narrative_summary.slice(0, 120)}…`
      : summary.narrative_summary
    : t("kb.wiki.notGenerated");

  const buttonText = summary.status === "pending" ? t("kb.wiki.generate") : t("kb.wiki.refresh");

  return (
    <div className="flex items-start gap-3 py-3 px-3 rounded-md hover:bg-muted/30 transition-colors">
      <div className="mt-1.5 shrink-0">
        <WikiStatusDot status={summary.status} size="sm" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{entityName}</p>
        <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">{label}</p>
        {summary.role_in_story && (
          <span className="inline-block mt-1 px-2 py-0.5 bg-primary/10 text-primary text-xs font-medium rounded-full">
            {summary.role_in_story}
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={() => refreshMutation.mutate({ entityId: summary.entity_id })}
        disabled={isRefreshing}
        className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1.5 text-xs border border-border rounded-md
          hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label={buttonText}
      >
        {isRefreshing ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <RefreshCw className="w-3.5 h-3.5" />
        )}
        <span className="hidden sm:inline">{buttonText}</span>
      </button>
    </div>
  );
}
