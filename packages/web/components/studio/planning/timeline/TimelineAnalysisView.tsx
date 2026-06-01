"use client";

import { AlertTriangle, CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useTimelineAnalysis } from "@/lib/hooks/useTimeline";

/** Simple content-based key for list items without unique IDs. */
function contentKey(prefix: string, content: string, idx: number): string {
  // Use a hash of the content for stable keys
  let hash = 0;
  for (let i = 0; i < content.length; i++) {
    hash = ((hash << 5) - hash + content.charCodeAt(i)) | 0;
  }
  return `${prefix}-${hash}-${idx}`;
}

interface TimelineAnalysisViewProps {
  novelId: string;
}

/** Displays AI-generated timeline analysis: events, conflicts, gaps, and assessment. */
export function TimelineAnalysisView({ novelId }: TimelineAnalysisViewProps) {
  const t = useTranslations("timeline");
  const { data: analysis, isLoading, error, refetch } = useTimelineAnalysis(novelId);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-3">
        <p className="text-sm text-[var(--color-error)]">{t("errorAnalysis")}</p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md border border-border hover:bg-[var(--color-bg-secondary)] transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          {t("runAnalysis")}
        </button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">{t("runningAnalysis")}</span>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-3">
        <p className="text-sm text-muted-foreground">{t("noAnalysis")}</p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          {t("runAnalysis")}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Run Analysis button */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => void refetch()}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md border border-border hover:bg-[var(--color-bg-secondary)] transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          {t("runAnalysis")}
        </button>
      </div>

      {/* Timeline Events (chronological) */}
      {analysis.timeline_events.length > 0 && (
        <section>
          <h4 className="text-sm font-medium mb-2">{t("eventsTab")}</h4>
          <div className="flex flex-col gap-2">
            {analysis.timeline_events.map((event, index) => (
              <div
                key={contentKey("ae", event.event_name, index)}
                className="p-3 rounded-lg border border-border bg-card"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{event.event_name}</span>
                  {event.timestamp && (
                    <span className="text-xs text-muted-foreground">{event.timestamp}</span>
                  )}
                </div>
                {event.description && (
                  <p className="text-xs text-muted-foreground mt-1">{event.description}</p>
                )}
                {event.characters_involved.length > 0 && (
                  <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                    {event.characters_involved.map((char) => (
                      <span
                        key={char}
                        className="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded-full bg-[var(--color-bg-secondary)] text-muted-foreground"
                      >
                        {char}
                      </span>
                    ))}
                  </div>
                )}
                {event.location && (
                  <div className="text-[11px] text-muted-foreground mt-1">📍 {event.location}</div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Temporal Conflicts */}
      <section>
        <h4 className="text-sm font-medium mb-2 flex items-center gap-1.5">
          <AlertTriangle className="w-4 h-4 text-[var(--color-warning)]" />
          {t("temporalConflicts")}
        </h4>
        {analysis.temporal_conflicts.length === 0 ? (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
            {t("conflictsNone")}
          </div>
        ) : (
          <ul className="flex flex-col gap-1">
            {analysis.temporal_conflicts.map((conflict, index) => (
              <li
                key={contentKey("cf", conflict, index)}
                className="text-xs text-[var(--color-text-primary)] p-2 rounded border border-border bg-card"
              >
                {conflict}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Coverage Gaps */}
      <section>
        <h4 className="text-sm font-medium mb-2 flex items-center gap-1.5">
          <AlertTriangle className="w-4 h-4 text-[var(--color-warning)]" />
          {t("coverageGaps")}
        </h4>
        {analysis.coverage_gaps.length === 0 ? (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
            {t("gapsNone")}
          </div>
        ) : (
          <ul className="flex flex-col gap-1">
            {analysis.coverage_gaps.map((gap, index) => (
              <li
                key={contentKey("gp", gap, index)}
                className="text-xs text-[var(--color-text-primary)] p-2 rounded border border-border bg-card"
              >
                {gap}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Overall Assessment */}
      {analysis.overall_assessment && (
        <section>
          <h4 className="text-sm font-medium mb-2">{t("overallAssessment")}</h4>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {analysis.overall_assessment}
          </p>
        </section>
      )}
    </div>
  );
}
