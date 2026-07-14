"use client";

/**
 * Worldbuilding analysis card sub-components.
 *
 * GapCard, ConnectionCard, and groupByCategory helper.
 * ConsistencyCard is extracted to its own module (RULE-04) and re-exported
 * here for backward-compatible imports.
 *
 * Extracted from WorldbuildingAnalysisPanel.tsx per RULE-04.
 */

import { Check, ChevronRight } from "lucide-react";
import type { ConnectionSuggestion, ConsistencyIssue, GapFinding } from "@/lib/api/worldbuilding";
import { SEVERITY_COLORS } from "./severityStyles";

// Re-export for backward-compatible imports (ConsistencyResults, AnalysisTabs, tests).
export { ConsistencyCard } from "./ConsistencyCard";
export { SEVERITY_COLORS };

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
            {t("worldbuilding.relatedType")}: {gap.related_entity_type}
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
              {Math.round(connection.confidence * 100)}% {t("worldbuilding.confidence")}
            </span>
          </div>
        </div>
        {isSelected && (
          <span className="text-xs text-green-600 dark:text-green-400 flex-shrink-0">
            {t("kb.willApply")}
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
