"use client";

/**
 * ConsistencyIssueList — filterable issue card list for ConsistencyPanel.
 *
 * Extracted from ConsistencyPanel to keep it under RULE-04 limit.
 * Filters issues by check type and severity, renders as cards.
 */

import { ChevronDown, ChevronUp, Lightbulb, MapPin } from "lucide-react";
import { useState } from "react";
import type {
  ConsistencyCheckType,
  ConsistencyIssue,
  ConsistencySeverity,
} from "@/lib/api/analysis";

// --- Severity badge styling ---

const SEVERITY_STYLES: Record<ConsistencySeverity, string> = {
  error: "bg-red-100 text-red-700 dark:bg-red-950/30 dark:text-red-400",
  warning: "bg-amber-100 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400",
  info: "bg-blue-100 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400",
};

const SEVERITY_DOT: Record<ConsistencySeverity, string> = {
  error: "bg-red-500",
  warning: "bg-amber-500",
  info: "bg-blue-500",
};

const SEVERITY_BORDER: Record<ConsistencySeverity, string> = {
  error: "border-l-red-400 dark:border-l-red-500",
  warning: "border-l-amber-400 dark:border-l-amber-500",
  info: "border-l-blue-400 dark:border-l-blue-500",
};

// --- Check type labels (not i18n-ed yet, using display names) ---

const CHECK_TYPE_LABELS: Record<ConsistencyCheckType, string> = {
  character: "Character",
  timeline: "Timeline",
  world: "World",
  plot: "Plot",
};

const CHECK_TYPE_STYLES: Record<ConsistencyCheckType, string> = {
  character: "bg-purple-100 text-purple-700 dark:bg-purple-950/30 dark:text-purple-400",
  timeline: "bg-blue-100 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400",
  world: "bg-teal-100 text-teal-700 dark:bg-teal-950/30 dark:text-teal-400",
  plot: "bg-orange-100 text-orange-700 dark:bg-orange-950/30 dark:text-orange-400",
};

// --- Types ---

interface ConsistencyIssueListProps {
  issues: ConsistencyIssue[];
  t: (key: string, params?: Record<string, unknown>) => string;
}

// --- Single issue card ---

function IssueCard({ issue, t }: { issue: ConsistencyIssue; t: (key: string) => string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`rounded-lg border border-border border-l-2 p-4 ${SEVERITY_BORDER[issue.severity]}`}
    >
      {/* Header: severity + check type badges */}
      <div className="flex items-start gap-2 mb-2">
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${SEVERITY_STYLES[issue.severity]}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${SEVERITY_DOT[issue.severity]}`} />
          {t(`consistency.severity.${issue.severity}`)}
        </span>
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium ${CHECK_TYPE_STYLES[issue.check_type]}`}
        >
          {CHECK_TYPE_LABELS[issue.check_type]}
        </span>
      </div>

      {/* Description */}
      <p className="text-sm mb-2">{issue.description}</p>

      {/* Expandable details */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        aria-expanded={expanded}
      >
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {expanded ? t("consistency.detailsHide") : t("consistency.detailsShow")}
      </button>

      {expanded && (
        <div className="mt-2 space-y-2 pl-2">
          {/* Locations */}
          {issue.locations.length > 0 && (
            <div>
              <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground mb-1">
                <MapPin className="w-3 h-3" />
                {t("consistency.locations")}
              </div>
              <ul className="text-xs text-muted-foreground space-y-0.5">
                {issue.locations.map((loc) => (
                  <li key={`loc-${loc.slice(0, 40)}`}>{loc}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Conflicting facts */}
          {issue.conflicting_facts.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">
                {t("consistency.conflictingFacts")}
              </p>
              <ul className="text-xs text-muted-foreground space-y-0.5">
                {issue.conflicting_facts.map((fact) => (
                  <li key={`fact-${fact.slice(0, 40)}`} className="pl-2 border-l border-muted">
                    {fact}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Suggestion */}
          {issue.suggestion && (
            <div className="p-2 rounded bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/50">
              <div className="flex items-center gap-1 text-xs font-medium text-amber-700 dark:text-amber-400 mb-1">
                <Lightbulb className="w-3 h-3" />
                {t("consistency.suggestion")}
              </div>
              <p className="text-xs text-amber-800 dark:text-amber-300">{issue.suggestion}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// --- Component ---

export function ConsistencyIssueList({ issues, t }: ConsistencyIssueListProps) {
  const [filterType, setFilterType] = useState<ConsistencyCheckType | "all">("all");
  const [filterSeverity, setFilterSeverity] = useState<ConsistencySeverity | "all">("all");

  const filteredIssues = issues.filter((issue) => {
    if (filterType !== "all" && issue.check_type !== filterType) return false;
    if (filterSeverity !== "all" && issue.severity !== filterSeverity) return false;
    return true;
  });

  return (
    <div className="space-y-3">
      {/* Filter controls */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Check type filter */}
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value as ConsistencyCheckType | "all")}
          className="text-xs border border-border rounded-md px-2 py-1 bg-background"
          aria-label={t("consistency.filterByType")}
        >
          <option value="all">{t("consistency.allTypes")}</option>
          {Object.entries(CHECK_TYPE_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>

        {/* Severity filter */}
        <select
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value as ConsistencySeverity | "all")}
          className="text-xs border border-border rounded-md px-2 py-1 bg-background"
          aria-label={t("consistency.filterBySeverity")}
        >
          <option value="all">{t("consistency.allSeverities")}</option>
          <option value="error">{t("consistency.severity.error")}</option>
          <option value="warning">{t("consistency.severity.warning")}</option>
          <option value="info">{t("consistency.severity.info")}</option>
        </select>

        <span className="text-xs text-muted-foreground">
          {t("consistency.issueCount", { count: filteredIssues.length, total: issues.length })}
        </span>
      </div>

      {/* Issue cards */}
      {filteredIssues.length > 0 ? (
        <div className="space-y-3">
          {filteredIssues.map((issue) => (
            <IssueCard
              key={`issue-${issue.check_type}-${issue.severity}-${issue.description.slice(0, 30)}`}
              issue={issue}
              t={t}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <p className="text-sm text-muted-foreground">{t("consistency.noIssues")}</p>
        </div>
      )}
    </div>
  );
}
