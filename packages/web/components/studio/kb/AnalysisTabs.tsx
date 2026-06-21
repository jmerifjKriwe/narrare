"use client";

/**
 * AnalysisTabs — Tab content renderer for worldbuilding analysis.
 *
 * Renders Gaps, Connections, or Consistency tab content.
 * Extracted from WorldbuildingAnalysisPanel for RULE-04 compliance.
 */

import { useTranslations } from "next-intl";
import type { WorldbuildingAnalysisResponse } from "@/lib/api/worldbuilding";
import {
  ConnectionCard,
  ConsistencyCard,
  GapCard,
  groupByCategory,
} from "./WorldbuildingAnalysisCards";

type AnalysisTab = "gaps" | "connections" | "consistency";

const SEVERITY_ORDER: Record<string, number> = { critical: 0, major: 1, minor: 2, info: 3 };

interface AnalysisTabsProps {
  readonly activeTab: AnalysisTab;
  readonly analysis: WorldbuildingAnalysisResponse;
  readonly selectedConnectionIndices: Set<number>;
  readonly onToggleConnection: (index: number) => void;
  readonly onSelectAll: () => void;
  readonly onSelectNone: () => void;
}

export function AnalysisTabs({
  activeTab,
  analysis,
  selectedConnectionIndices,
  onToggleConnection,
  onSelectAll,
  onSelectNone,
}: AnalysisTabsProps) {
  const t = useTranslations("studio");

  const sortedGaps = [...analysis.gap_findings].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99),
  );
  const connections = analysis.connection_suggestions;
  const consistencyIssues = analysis.consistency_issues;
  const groupedConsistency = groupByCategory(consistencyIssues);

  switch (activeTab) {
    case "gaps":
      return sortedGaps.length > 0 ? (
        <div className="space-y-3">
          {sortedGaps.map((gap) => (
            <GapCard
              key={`${gap.entity_id ?? "none"}-${gap.gap_type}-${gap.field_key ?? "body"}`}
              gap={gap}
              t={t}
            />
          ))}
        </div>
      ) : null;

    case "connections":
      return connections.length > 0 ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
            <span className="text-sm text-muted-foreground">
              {t("worldbuilding.selectedCount", {
                count: selectedConnectionIndices.size,
                total: connections.length,
              })}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onSelectAll}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                {t("kb.selectAll")}
              </button>
              <span className="text-muted-foreground">|</span>
              <button
                type="button"
                onClick={onSelectNone}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                {t("kb.selectNone")}
              </button>
            </div>
          </div>
          {connections.map((conn) => (
            <ConnectionCard
              key={conn.finding_index}
              connection={conn}
              isSelected={selectedConnectionIndices.has(conn.finding_index)}
              onToggle={() => onToggleConnection(conn.finding_index)}
              t={t}
            />
          ))}
        </div>
      ) : null;

    case "consistency":
      return consistencyIssues.length > 0 ? (
        <div className="space-y-6">
          {Object.entries(groupedConsistency).map(([category, issues]) => (
            <div key={category}>
              <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">
                {category}
              </h4>
              <div className="space-y-3">
                {issues.map((issue) => (
                  <ConsistencyCard key={issue.finding_index} issue={issue} t={t} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null;
  }
}
