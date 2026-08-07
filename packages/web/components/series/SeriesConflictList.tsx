"use client";

/**
 * SeriesConflictList — renders the canon contradictions found by a
 * series-consistency check (Spec 4 Task 4).
 *
 * Pure presentational component (mirrors the read-only display convention of
 * `SeriesVoiceProfileView`). Each conflict shows a severity badge (`error` =
 * hard contradiction, `warning` = possible issue), the contradicted Canon entry
 * name, what Canon says, the verbatim chapter excerpt, and the agent's
 * explanation. An **empty** list renders the positive "no conflicts" state
 * (no contradictions is a valid, common result).
 *
 * All copy via ``useTranslations("studio")`` under ``series.drift.*``.
 */
import { useTranslations } from "next-intl";
import type { CanonConflict, CanonConflictSeverity } from "@/types";

interface SeriesConflictListProps {
  /** The canon contradictions found (possibly empty — no contradictions). */
  readonly conflicts: CanonConflict[];
  /** The agent's 1-2 sentence overall assessment (optional). */
  readonly summary?: string;
}

function severityBadgeClass(severity: CanonConflictSeverity): string {
  return severity === "error"
    ? "bg-destructive/15 text-destructive"
    : "bg-amber-500/15 text-amber-700 dark:text-amber-400";
}

export function SeriesConflictList({ conflicts, summary }: SeriesConflictListProps) {
  const t = useTranslations("studio");

  return (
    <div data-testid="series-conflicts-list" className="space-y-2">
      {summary ? <p className="text-sm text-muted-foreground">{summary}</p> : null}
      {conflicts.length === 0 ? (
        <p
          data-testid="series-conflicts-empty"
          className="rounded-md border border-dashed p-4 text-sm text-muted-foreground"
        >
          {t("series.drift.noConflicts")}
        </p>
      ) : (
        <ul className="space-y-2">
          {conflicts.map((conflict) => (
            <li
              key={`${conflict.canon_entry_slug}-${conflict.chapter_text_excerpt}`}
              data-testid="series-conflict-item"
              className="space-y-1 rounded-md border border-border bg-card p-3 text-sm"
            >
              <div className="flex items-center gap-2">
                <span
                  data-testid={`series-conflict-severity-${conflict.severity}`}
                  className={`rounded px-1.5 py-0.5 text-xs font-medium ${severityBadgeClass(conflict.severity)}`}
                >
                  {t(`series.drift.severity.${conflict.severity}`)}
                </span>
                <span className="font-medium text-foreground">{conflict.canon_entry_name}</span>
              </div>
              <p className="text-muted-foreground">
                <span className="text-foreground/70">{t("series.drift.canonStatement")}:</span>{" "}
                {conflict.canon_statement}
              </p>
              <p className="text-muted-foreground">
                <span className="text-foreground/70">{t("series.drift.excerpt")}:</span>{" "}
                <span className="italic">{conflict.chapter_text_excerpt}</span>
              </p>
              <p className="text-foreground">{conflict.explanation}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
