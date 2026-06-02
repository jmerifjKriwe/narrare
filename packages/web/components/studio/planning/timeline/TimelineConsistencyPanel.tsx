"use client";

import { AlertTriangle, CheckCircle2, Info, Loader2, RefreshCw, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useTimelineConsistency } from "@/lib/hooks/useTimeline";
import { cn } from "@/lib/utils";
import type { TemporalIssue } from "@/types/timeline";

interface TimelineConsistencyPanelProps {
  novelId: string;
}

/** Severity icon mapping. */
const SEVERITY_ICONS: Record<TemporalIssue["severity"], typeof XCircle> = {
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

/** Severity color classes. */
const SEVERITY_STYLES: Record<TemporalIssue["severity"], string> = {
  error: "text-[var(--color-error)]",
  warning: "text-[var(--color-warning)]",
  info: "text-blue-500",
};

/** Severity badge classes. */
const SEVERITY_BADGE: Record<TemporalIssue["severity"], string> = {
  error: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  warning: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  info: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
};

/** Source badge i18n key mapping. */
const SOURCE_LABELS: Record<TemporalIssue["source"], string> = {
  deterministic: "sourceDeterministic",
  llm: "sourceLlm",
};

/** Displays temporal consistency check results grouped by severity. */
export function TimelineConsistencyPanel({ novelId }: TimelineConsistencyPanelProps) {
  const t = useTranslations("timeline");
  const { data: consistency, isLoading, error, refetch } = useTimelineConsistency(novelId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">{t("checking")}</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-3">
        <p className="text-sm text-[var(--color-error)]">{t("errorConsistency")}</p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md border border-border hover:bg-[var(--color-bg-secondary)] transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          {t("recheck")}
        </button>
      </div>
    );
  }

  if (!consistency) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-3">
        <p className="text-sm text-muted-foreground">{t("noIssues")}</p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          {t("recheck")}
        </button>
      </div>
    );
  }

  // Group issues by severity: errors first, then warnings, then info
  const sortedIssues = [...consistency.issues].sort((a, b) => {
    const order: Record<TemporalIssue["severity"], number> = { error: 0, warning: 1, info: 2 };
    return order[a.severity] - order[b.severity];
  });

  const errorCount = consistency.issues.filter((i) => i.severity === "error").length;
  const warningCount = consistency.issues.filter((i) => i.severity === "warning").length;
  const hasNoIssues = consistency.issues.length === 0;

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Overall assessment */}
      <div className="flex items-center gap-2">
        {hasNoIssues ? (
          <>
            <CheckCircle2 className="w-4 h-4 text-green-500" />
            <span className="text-sm font-medium text-[var(--color-text-primary)]">
              {t("noIssues")}
            </span>
          </>
        ) : (
          <>
            <AlertTriangle className="w-4 h-4 text-[var(--color-warning)]" />
            <span className="text-sm font-medium text-[var(--color-text-primary)]">
              {errorCount > 0 && t("hasErrors", { count: errorCount })}
              {errorCount > 0 && warningCount > 0 && " "}
              {warningCount > 0 && t("hasWarnings", { count: warningCount })}
            </span>
          </>
        )}
      </div>

      {/* Issues list */}
      {sortedIssues.length > 0 && (
        <div className="flex flex-col gap-3">
          {sortedIssues.map((issue, index) => {
            const SeverityIcon = SEVERITY_ICONS[issue.severity];
            const stableKey = `${issue.rule_id}-${issue.event_ids.join(",")}-${index}`;
            return (
              <div key={stableKey} className="p-3 rounded-lg border border-border bg-card">
                {/* Severity icon + rule ID badge */}
                <div className="flex items-center gap-2 flex-wrap">
                  <SeverityIcon className={cn("w-4 h-4", SEVERITY_STYLES[issue.severity])} />
                  <span
                    className={cn(
                      "inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded-full uppercase",
                      SEVERITY_BADGE[issue.severity],
                    )}
                  >
                    {t(issue.severity)}
                  </span>
                  <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-[var(--color-bg-secondary)] text-muted-foreground">
                    {t("ruleId")}: {issue.rule_id}
                  </span>
                  <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-[var(--color-bg-secondary)] text-muted-foreground">
                    {t(SOURCE_LABELS[issue.source])}
                  </span>
                </div>

                {/* Affected events */}
                {issue.event_ids.length > 0 && (
                  <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                    <span className="text-[10px] text-muted-foreground">
                      {t("affectedEvents")}:
                    </span>
                    {issue.event_ids.map((eventId) => (
                      <span
                        key={eventId}
                        className="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded-full bg-[var(--color-bg-secondary)] text-muted-foreground"
                      >
                        {eventId}
                      </span>
                    ))}
                  </div>
                )}

                {/* Description */}
                <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
                  {issue.description}
                </p>

                {/* Suggestion */}
                <div className="flex items-start gap-1.5 mt-1.5">
                  <span className="text-xs" aria-hidden="true">
                    {"\uD83D\uDCA1"}
                  </span>
                  <p className="text-xs text-muted-foreground">
                    {t("fix")}: {issue.suggestion}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Re-check button */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => void refetch()}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md border border-border hover:bg-[var(--color-bg-secondary)] transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          {t("recheck")}
        </button>
      </div>
    </div>
  );
}
