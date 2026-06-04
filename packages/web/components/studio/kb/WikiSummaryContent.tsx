"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import type { WikiSummaryResponse } from "@/lib/api/wiki";

// --- Helpers ---

/** Format an ISO date string as relative time (e.g. "2 hours ago"). */
function formatRelativeTime(dateStr: string | null, t: (key: string) => string): string | null {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return t("kb.wiki.justNow");
  if (diffMinutes < 60) return t("kb.wiki.minutesAgo").replace("{count}", String(diffMinutes));
  if (diffHours < 24) return t("kb.wiki.hoursAgo").replace("{count}", String(diffHours));
  return t("kb.wiki.daysAgo").replace("{count}", String(diffDays));
}

interface WikiSummaryContentProps {
  summary: WikiSummaryResponse;
  entityType: string;
  isRefreshing: boolean;
  hasRefreshError: boolean;
  onRefresh: () => void;
}

export function WikiSummaryContent({
  summary,
  entityType,
  isRefreshing,
  hasRefreshError,
  onRefresh,
}: WikiSummaryContentProps) {
  const t = useTranslations("studio");
  const relativeTime = formatRelativeTime(summary.generated_at, t);

  return (
    <div className="px-4 py-4 space-y-4">
      {/* Narrative summary */}
      <div>
        <h4 className="text-xs font-medium text-muted-foreground mb-1.5">
          {t("kb.wiki.narrativeSummary")}
        </h4>
        <p className="text-sm leading-relaxed">{summary.narrative_summary}</p>
      </div>

      {/* Role in story */}
      {summary.role_in_story && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground mb-1.5">
            {t("kb.wiki.roleInStory")}
          </h4>
          <span className="inline-block px-2.5 py-1 bg-primary/10 text-primary text-xs font-medium rounded-full">
            {summary.role_in_story}
          </span>
        </div>
      )}

      {/* Key attributes */}
      {summary.key_attributes && summary.key_attributes.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground mb-1.5">
            {t("kb.wiki.keyAttributes")}
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {summary.key_attributes.map((attr) => (
              <span
                key={attr}
                className="inline-block px-2 py-0.5 bg-muted text-xs rounded-md text-muted-foreground"
              >
                {attr}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Relationships */}
      {summary.relationships && summary.relationships.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground mb-1.5">
            {t("kb.wiki.relationships")}
          </h4>
          <ul className="space-y-1">
            {summary.relationships.map((rel) => (
              <li
                key={`rel-${(rel.name as string) ?? (rel.entity_id as string) ?? JSON.stringify(rel)}`}
                className="text-sm text-muted-foreground"
              >
                {(rel.name as string) ?? (rel.label as string) ?? JSON.stringify(rel)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Character arc (only for characters) */}
      {summary.character_arc && entityType === "character" && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground mb-1.5">
            {t("kb.wiki.characterArc")}
          </h4>
          <p className="text-sm italic leading-relaxed text-muted-foreground">
            {summary.character_arc}
          </p>
        </div>
      )}

      {/* Footer: generated time + refresh button */}
      <div className="flex items-center justify-between pt-2 border-t border-border/30">
        <div className="flex items-center gap-3">
          {relativeTime && (
            <span className="text-xs text-muted-foreground">
              {t("kb.wiki.generatedAt").replace("{time}", relativeTime)}
            </span>
          )}
          {summary.version > 0 && (
            <span className="text-xs text-muted-foreground">
              {t("kb.wiki.version").replace("{version}", String(summary.version))}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isRefreshing ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {t("kb.wiki.refreshing")}
            </>
          ) : (
            <>
              <RefreshCw className="w-3.5 h-3.5" />
              {t("kb.wiki.refresh")}
            </>
          )}
        </button>
      </div>

      {/* Refresh error */}
      {hasRefreshError && <p className="text-xs text-destructive">{t("kb.wiki.refreshError")}</p>}
    </div>
  );
}
