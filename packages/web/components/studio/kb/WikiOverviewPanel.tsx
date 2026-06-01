"use client";

/**
 * WikiOverviewPanel — Shows all wiki summaries with status overview.
 *
 * Displays index stats (fresh/stale/pending), entity summaries grouped
 * by status, and actions for refreshing stale or marking all stale.
 */

import { AlertTriangle, BookOpen, Loader2, RefreshCw, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo } from "react";
import type { WikiSummaryResponse } from "@/lib/api/wiki";
import {
  useWikiIndex,
  useWikiMarkStale,
  useWikiRefresh,
  useWikiSummaries,
} from "@/lib/hooks/useWiki";

// --- Status indicator ---

interface StatusDotProps {
  status: "fresh" | "stale" | "pending";
}

function StatusDot({ status }: StatusDotProps) {
  const colorMap = {
    fresh: "bg-green-500",
    stale: "bg-yellow-500",
    pending: "bg-gray-400",
  };
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${colorMap[status]}`} />;
}

// --- Entity Summary Card ---

interface EntitySummaryCardProps {
  summary: WikiSummaryResponse;
  refreshMutation: ReturnType<typeof useWikiRefresh>;
}

function EntitySummaryCard({ summary, refreshMutation }: EntitySummaryCardProps) {
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
        <StatusDot status={summary.status} />
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

// --- Props ---

interface WikiOverviewPanelProps {
  novelId: string;
  onClose: () => void;
}

// --- Component ---

export function WikiOverviewPanel({ novelId, onClose }: WikiOverviewPanelProps) {
  const t = useTranslations("studio");

  const { data: indexData, isLoading: indexLoading, isError: indexError } = useWikiIndex(novelId);
  const {
    data: summariesData,
    isLoading: summariesLoading,
    isError: summariesError,
  } = useWikiSummaries(novelId);
  const refreshMutation = useWikiRefresh(novelId);
  const markStaleMutation = useWikiMarkStale(novelId);

  const isLoading = indexLoading || summariesLoading;
  const isError = indexError || summariesError;

  // Sort: stale first (needs attention), then pending, then fresh
  const sortedSummaries = useMemo(() => {
    const items = summariesData?.items ?? [];
    const priority: Record<string, number> = { stale: 0, pending: 1, fresh: 2 };
    return [...items].sort((a, b) => (priority[a.status] ?? 3) - (priority[b.status] ?? 3));
  }, [summariesData]);

  const relativeTime = useMemo(() => {
    const dateStr = indexData?.last_generated_at;
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
  }, [indexData?.last_generated_at, t]);
  const staleCount = indexData?.stale_count ?? 0;
  const pendingCount = indexData?.pending_count ?? 0;

  // Loading state
  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col h-full border-l border-border bg-card">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-medium">{t("kb.wiki.overviewTitle")}</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-muted"
            aria-label={t("kb.wiki.close")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="w-4 h-4 animate-spin" />
            {t("kb.wiki.loading")}
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="flex-1 flex flex-col h-full border-l border-border bg-card">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-medium">{t("kb.wiki.overviewTitle")}</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-muted"
            aria-label={t("kb.wiki.close")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <p className="text-sm text-destructive">{t("kb.wiki.loadError")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full border-l border-border bg-card">
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-primary" />
          <h2 className="text-sm font-medium">{t("kb.wiki.overviewTitle")}</h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded hover:bg-muted"
          aria-label={t("kb.wiki.close")}
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Index Stats */}
        <div className="border border-border/50 rounded-lg p-4 space-y-2">
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            {t("kb.wiki.indexStats")}
          </h3>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <span className="flex items-center gap-1.5">
              <StatusDot status="fresh" />
              {t("kb.wiki.fresh")}: {indexData?.fresh_count ?? 0}
            </span>
            <span className="flex items-center gap-1.5">
              <StatusDot status="stale" />
              {t("kb.wiki.stale")}: {staleCount}
            </span>
            <span className="flex items-center gap-1.5">
              <StatusDot status="pending" />
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

        {/* Actions */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => {
              // Refresh all stale summaries
              const staleIds = sortedSummaries
                .filter((s) => s.status === "stale")
                .map((s) => s.entity_id);
              for (const entityId of staleIds) {
                refreshMutation.mutate({ entityId });
              }
            }}
            disabled={staleCount === 0 || refreshMutation.isPending}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm
              border border-border rounded-md hover:bg-muted transition-colors
              disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${refreshMutation.isPending ? "animate-spin" : ""}`}
            />
            {t("kb.wiki.refreshStale")}
          </button>
          <button
            type="button"
            onClick={() => markStaleMutation.mutate(undefined)}
            disabled={markStaleMutation.isPending}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm
              border border-yellow-500/50 text-yellow-700 dark:text-yellow-400 rounded-md
              hover:bg-yellow-50 dark:hover:bg-yellow-900/20 transition-colors
              disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            {t("kb.wiki.markAllStale")}
          </button>
        </div>

        {/* Mark stale error */}
        {markStaleMutation.isError && (
          <p className="text-xs text-destructive">{t("kb.wiki.refreshError")}</p>
        )}

        {/* Entity Summaries */}
        <div className="space-y-0.5">
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
            {t("kb.wiki.entitySummaries")}
          </h3>

          {sortedSummaries.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center">
              {t("kb.wiki.noSummaries")}
            </p>
          ) : (
            sortedSummaries.map((summary) => (
              <EntitySummaryCard
                key={summary.entity_id}
                summary={summary}
                refreshMutation={refreshMutation}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
