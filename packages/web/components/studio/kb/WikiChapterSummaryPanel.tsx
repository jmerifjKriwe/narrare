"use client";

/**
 * WikiChapterSummaryPanel — Shows wiki summary for a single chapter.
 *
 * Collapsible panel displaying narrative summary, key events,
 * entities involved, themes, and emotional arc.
 */

import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { useWikiChapterSummary } from "@/lib/hooks/useWiki";

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
  return <span className={`inline-block w-2 h-2 rounded-full ${colorMap[status]}`} />;
}

const STATUS_LABELS: Record<string, string> = {
  fresh: "kb.wiki.statusFresh",
  stale: "kb.wiki.statusStale",
  pending: "kb.wiki.statusPending",
};

// --- Props ---

interface WikiChapterSummaryPanelProps {
  novelId: string;
  chapterId: string;
  chapterTitle?: string;
}

// --- Component ---

export function WikiChapterSummaryPanel({
  novelId,
  chapterId,
  chapterTitle: _chapterTitle,
}: WikiChapterSummaryPanelProps) {
  const t = useTranslations("studio");
  const [isCollapsed, setIsCollapsed] = useState(true);

  const { data: summary, isLoading, isError } = useWikiChapterSummary(novelId, chapterId);

  const relativeTime = useMemo(() => {
    const dateStr = summary?.generated_at;
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
  }, [summary?.generated_at, t]);

  const statusLabel = summary
    ? STATUS_LABELS[summary.status]
      ? t(STATUS_LABELS[summary.status])
      : summary.status
    : "";

  // Extract entity names from entities_involved
  const entityNames = (summary?.entities_involved ?? []).map(
    (e) => (e.name as string) ?? (e.entity_id as string) ?? JSON.stringify(e),
  );

  // Loading state
  if (isLoading) {
    return (
      <div className="border border-border/50 rounded-lg p-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          {t("kb.wiki.loading")}
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="border border-border/50 rounded-lg p-4">
        <p className="text-sm text-muted-foreground">{t("kb.wiki.loadError")}</p>
      </div>
    );
  }

  // No summary available
  if (!summary) {
    return (
      <div className="border border-border/50 rounded-lg p-4">
        <p className="text-sm text-muted-foreground">{t("kb.wiki.noSummaryYet")}</p>
      </div>
    );
  }

  return (
    <div className="border border-border/50 rounded-lg overflow-hidden">
      {/* Collapsible header */}
      <button
        type="button"
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
        aria-expanded={!isCollapsed}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{t("kb.wiki.chapterWiki")}</span>
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <StatusDot status={summary.status} />
            {statusLabel}
          </span>
        </div>
        {isCollapsed ? (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        )}
      </button>

      {/* Content */}
      {!isCollapsed && (
        <div className="px-4 py-4 space-y-3">
          {/* Narrative summary */}
          {summary.narrative_summary && (
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                {t("kb.wiki.narrativeSummary")}
              </h4>
              <p className="text-sm leading-relaxed">{summary.narrative_summary}</p>
            </div>
          )}

          {/* Key events */}
          {summary.key_events && summary.key_events.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                {t("kb.wiki.keyEvents")}
              </h4>
              <ul className="space-y-0.5">
                {summary.key_events.map((event) => (
                  <li
                    key={event}
                    className="text-sm text-muted-foreground flex items-start gap-1.5"
                  >
                    <span className="mt-1.5 w-1 h-1 rounded-full bg-muted-foreground shrink-0" />
                    {event}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Entities involved */}
          {entityNames.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                {t("kb.wiki.entitiesInvolved")}
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {entityNames.map((name) => (
                  <span
                    key={name}
                    className="inline-block px-2 py-0.5 bg-primary/10 text-primary text-xs font-medium rounded-full"
                  >
                    {name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Themes */}
          {summary.themes && summary.themes.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                {t("kb.wiki.themes")}
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {summary.themes.map((theme) => (
                  <span
                    key={theme}
                    className="inline-block px-2 py-0.5 bg-muted text-xs rounded-md text-muted-foreground"
                  >
                    {theme}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Emotional arc */}
          {summary.emotional_arc && (
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                {t("kb.wiki.emotionalArc")}
              </h4>
              <p className="text-sm italic leading-relaxed text-muted-foreground">
                {summary.emotional_arc}
              </p>
            </div>
          )}

          {/* Status footer */}
          <div className="flex items-center gap-2 pt-2 border-t border-border/30">
            <StatusDot status={summary.status} />
            <span className="text-xs text-muted-foreground">
              {statusLabel}
              {relativeTime && ` (${relativeTime})`}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
