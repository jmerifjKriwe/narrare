"use client";

/**
 * WikiChapterSummaryPanel — Shows wiki summary for a single chapter.
 *
 * Collapsible panel displaying narrative summary, key events,
 * entities involved, themes, and emotional arc.
 */

import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useWikiChapterSummary } from "@/lib/hooks/useWiki";
import { ChapterSummaryContent } from "./ChapterSummaryContent";
import { useWikiRelativeTime } from "./useWikiRelativeTime";
import { WikiStatusDot } from "./WikiStatusDot";

// --- Status label mapping ---

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
  const relativeTime = useWikiRelativeTime(summary?.generated_at);

  const statusLabel = summary
    ? STATUS_LABELS[summary.status]
      ? t(STATUS_LABELS[summary.status])
      : summary.status
    : "";

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
            <WikiStatusDot status={summary.status} size="sm" />
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
        <ChapterSummaryContent
          summary={summary}
          statusLabel={statusLabel}
          relativeTime={relativeTime}
        />
      )}
    </div>
  );
}
