"use client";

/**
 * ChapterSummaryContent — Expandable content of a wiki chapter summary.
 *
 * Shows narrative summary, key events, entities, themes, and emotional arc.
 * Extracted from WikiChapterSummaryPanel for RULE-04 compliance.
 */

import { useTranslations } from "next-intl";
import type { WikiChapterSummaryResponse } from "@/lib/api/wiki";
import { WikiStatusDot } from "./WikiStatusDot";

interface ChapterSummaryContentProps {
  summary: WikiChapterSummaryResponse;
  statusLabel: string;
  relativeTime: string | null;
}

export function ChapterSummaryContent({
  summary,
  statusLabel,
  relativeTime,
}: ChapterSummaryContentProps) {
  const t = useTranslations("studio");

  const entityNames = (summary.entities_involved ?? []).map(
    (e) => (e.name as string) ?? (e.entity_id as string) ?? JSON.stringify(e),
  );

  return (
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
              <li key={event} className="text-sm text-muted-foreground flex items-start gap-1.5">
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
          <h4 className="text-xs font-medium text-muted-foreground mb-1">{t("kb.wiki.themes")}</h4>
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
        <WikiStatusDot status={summary.status} size="sm" />
        <span className="text-xs text-muted-foreground">
          {statusLabel}
          {relativeTime && ` (${relativeTime})`}
        </span>
      </div>
    </div>
  );
}
