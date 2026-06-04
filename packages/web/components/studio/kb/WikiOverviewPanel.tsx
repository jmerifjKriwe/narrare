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
import {
  useWikiIndex,
  useWikiMarkStale,
  useWikiRefresh,
  useWikiSummaries,
} from "@/lib/hooks/useWiki";
import { useWikiRelativeTime } from "./useWikiRelativeTime";
import { WikiEntitySummaryCard } from "./WikiEntitySummaryCard";
import { WikiIndexStats } from "./WikiIndexStats";

// --- Panel Header ---

interface PanelHeaderProps {
  onClose: () => void;
  title: string;
  closeLabel: string;
}

function PanelHeader({ onClose, title, closeLabel }: PanelHeaderProps) {
  return (
    <div className="p-4 border-b border-border flex items-center justify-between">
      <div className="flex items-center gap-2">
        <BookOpen className="w-4 h-4 text-primary" />
        <h2 className="text-sm font-medium">{title}</h2>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="p-1 rounded hover:bg-muted"
        aria-label={closeLabel}
      >
        <X className="w-4 h-4" />
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

  const relativeTime = useWikiRelativeTime(indexData?.last_generated_at);
  const staleCount = indexData?.stale_count ?? 0;

  // Loading state
  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col h-full border-l border-border bg-card">
        <PanelHeader
          onClose={onClose}
          title={t("kb.wiki.overviewTitle")}
          closeLabel={t("kb.wiki.close")}
        />
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
        <PanelHeader
          onClose={onClose}
          title={t("kb.wiki.overviewTitle")}
          closeLabel={t("kb.wiki.close")}
        />
        <div className="flex-1 flex items-center justify-center p-6">
          <p className="text-sm text-destructive">{t("kb.wiki.loadError")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full border-l border-border bg-card">
      <PanelHeader
        onClose={onClose}
        title={t("kb.wiki.overviewTitle")}
        closeLabel={t("kb.wiki.close")}
      />

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <WikiIndexStats indexData={indexData} relativeTime={relativeTime} />

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
              <WikiEntitySummaryCard
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
