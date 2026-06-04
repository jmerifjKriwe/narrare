"use client";

/**
 * WikiSummaryPanel — Shows how the AI understands a KB entity.
 *
 * Displays the AI-generated wiki summary including narrative overview,
 * role, attributes, relationships, and character arc.
 * Supports refresh with loading/error states.
 */

import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useWikiRefresh, useWikiSummary } from "@/lib/hooks/useWiki";
import { WikiSummaryContent } from "./WikiSummaryContent";

// --- Status indicator ---

interface StatusIndicatorProps {
  status: "fresh" | "stale" | "pending";
  label: string;
}

function StatusIndicator({ status, label }: StatusIndicatorProps) {
  const colorMap = {
    fresh: "bg-green-500",
    stale: "bg-yellow-500",
    pending: "bg-gray-400",
  };
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <span className={`inline-block w-2 h-2 rounded-full ${colorMap[status]}`} />
      {label}
    </span>
  );
}

// --- Props ---

interface WikiSummaryPanelProps {
  novelId: string;
  entityId: string;
  entityName: string;
  entityType: string;
}

// --- Component ---

export function WikiSummaryPanel({
  novelId,
  entityId,
  entityName: _entityName,
  entityType,
}: WikiSummaryPanelProps) {
  const t = useTranslations("studio");
  const [isCollapsed, setIsCollapsed] = useState(false);

  const { data: summary, isLoading, isError } = useWikiSummary(novelId, entityId);
  const refreshMutation = useWikiRefresh(novelId);

  const statusLabels: Record<string, string> = {
    fresh: t("kb.wiki.statusFresh"),
    stale: t("kb.wiki.statusStale"),
    pending: t("kb.wiki.statusPending"),
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="mt-6 border border-border/50 rounded-lg p-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          {t("kb.wiki.loading")}
        </div>
      </div>
    );
  }

  // Error state — only show if we don't have stale data
  if (isError && !summary) {
    return (
      <div className="mt-6 border border-border/50 rounded-lg p-4">
        <p className="text-sm text-muted-foreground">{t("kb.wiki.loadError")}</p>
      </div>
    );
  }

  // No summary available yet
  if (!summary) {
    return (
      <div className="mt-6 border border-border/50 rounded-lg p-6">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-medium text-muted-foreground">{t("kb.wiki.noWiki")}</span>
        </div>
        <p className="text-xs text-muted-foreground">{t("kb.wiki.noWikiDescription")}</p>
      </div>
    );
  }

  return (
    <div className="mt-6 border border-border/50 rounded-lg overflow-hidden">
      {/* Header */}
      <button
        type="button"
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
        aria-expanded={!isCollapsed}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">
            {t("kb.wiki.aiPerspective").replace("{type}", entityType)}
          </span>
          <StatusIndicator
            status={summary.status}
            label={statusLabels[summary.status] ?? summary.status}
          />
        </div>
        {isCollapsed ? (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        )}
      </button>

      {/* Content */}
      {!isCollapsed && (
        <WikiSummaryContent
          summary={summary}
          entityType={entityType}
          isRefreshing={refreshMutation.isPending}
          hasRefreshError={refreshMutation.isError}
          onRefresh={() => refreshMutation.mutate({ entityId })}
        />
      )}
    </div>
  );
}
