"use client";

/**
 * Worldbuilding analysis card sub-components.
 *
 * Extracted from WorldbuildingAnalysisPanel.tsx per RULE-04.
 */

import { Check, ChevronRight } from "lucide-react";
import type { ConnectionSuggestion, ConsistencyIssue, GapFinding } from "@/lib/api/worldbuilding";

// --- Severity badge colors (shared with panel) ---

export const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  major: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  minor: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  info: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
};

// --- Gap Card ---

interface GapCardProps {
  gap: GapFinding;
  t: (key: string) => string;
}

export function GapCard({ gap, t }: GapCardProps) {
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <div className="flex items-center justify-between p-3 bg-muted/30">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`text-xs px-2 py-0.5 rounded font-medium ${SEVERITY_COLORS[gap.severity] ?? SEVERITY_COLORS.info}`}
          >
            {gap.severity}
          </span>
          <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {gap.gap_type.replace(/_/g, " ")}
          </span>
        </div>
        {gap.entity_name && (
          <span className="text-xs text-muted-foreground truncate max-w-[200px]">
            {gap.entity_name}
          </span>
        )}
      </div>
      <div className="p-3">
        <p className="text-sm">{gap.description}</p>
        {gap.related_entity_type && (
          <p className="text-xs text-muted-foreground mt-2">
            {t("worldbuilding.relatedType") || "Related type"}: {gap.related_entity_type}
          </p>
        )}
      </div>
    </div>
  );
}

// --- Connection Card ---

interface ConnectionCardProps {
  connection: ConnectionSuggestion;
  isSelected: boolean;
  onToggle: () => void;
  t: (key: string) => string;
}

export function ConnectionCard({ connection, isSelected, onToggle, t }: ConnectionCardProps) {
  return (
    <div
      className={`border rounded-lg overflow-hidden transition-colors ${
        isSelected ? "border-primary/50 bg-primary/5" : "border-border bg-card"
      }`}
    >
      <button
        type="button"
        className="w-full flex items-center gap-3 p-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
        onClick={onToggle}
      >
        <div
          className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
            isSelected ? "bg-primary border-primary" : "border-muted-foreground/40"
          }`}
        >
          {isSelected && <Check className="w-3.5 h-3.5 text-primary-foreground" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium truncate">{connection.source_entity_name}</span>
            <ChevronRight className="w-3 h-3 text-muted-foreground flex-shrink-0" />
            <span className="font-medium truncate">{connection.target_entity_name}</span>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-purple-500">{connection.suggested_rel_type}</span>
            <span className="text-xs text-muted-foreground">
              {Math.round(connection.confidence * 100)}%{" "}
              {t("worldbuilding.confidence") || "confidence"}
            </span>
          </div>
        </div>
        {isSelected && (
          <span className="text-xs text-green-600 dark:text-green-400 flex-shrink-0">
            {t("kb.willApply") || "Will apply"}
          </span>
        )}
      </button>
      {connection.reasoning && (
        <div className="px-4 pb-3 pt-1">
          <p className="text-xs text-muted-foreground italic">{connection.reasoning}</p>
        </div>
      )}
    </div>
  );
}

// --- Consistency Card ---

interface ConsistencyCardProps {
  issue: ConsistencyIssue;
  t: (key: string) => string;
}

export function ConsistencyCard({ issue, t }: ConsistencyCardProps) {
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <div className="flex items-center justify-between p-3 bg-muted/30">
        <div className="flex items-center gap-2">
          <span
            className={`text-xs px-2 py-0.5 rounded font-medium ${SEVERITY_COLORS[issue.severity] ?? SEVERITY_COLORS.info}`}
          >
            {issue.severity}
          </span>
          <span className="text-xs text-muted-foreground">
            {Math.round(issue.confidence * 100)}% {t("worldbuilding.confidence") || "confidence"}
          </span>
        </div>
        <span className="text-xs text-muted-foreground">
          {issue.entity_names.length} {t("worldbuilding.entities") || "entities"}
        </span>
      </div>
      <div className="p-3 space-y-2">
        <p className="text-sm">{issue.description}</p>
        <div className="p-2 bg-muted/20 rounded text-sm text-muted-foreground">
          <span className="font-medium">
            {t("worldbuilding.contradiction") || "Contradiction"}:
          </span>{" "}
          {issue.contradiction}
        </div>
        {issue.suggested_resolution && (
          <div className="p-2 bg-green-50 dark:bg-green-950/20 rounded text-sm">
            <span className="font-medium text-green-700 dark:text-green-400">
              {t("worldbuilding.resolution") || "Suggested resolution"}:
            </span>{" "}
            <span className="text-green-600 dark:text-green-400">{issue.suggested_resolution}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// --- Helpers ---

export function groupByCategory(issues: ConsistencyIssue[]): Record<string, ConsistencyIssue[]> {
  const groups: Record<string, ConsistencyIssue[]> = {};
  for (const issue of issues) {
    const key = issue.category;
    if (!groups[key]) {
      groups[key] = [];
    }
    groups[key].push(issue);
  }
  return groups;
}
