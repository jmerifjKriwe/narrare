"use client";

/**
 * WorldbuildingAnalysisPanel — AI-powered worldbuilding analysis.
 *
 * Shows analysis results with 3 tabs (Gaps, Connections, Consistency)
 * plus a score header. Connections tab supports multi-select and apply.
 *
 * Auto-triggers analysis on mount. Follows KBImprovePanel patterns.
 * Sub-components extracted to WorldbuildingAnalysisCards.tsx (RULE-04).
 */

import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Link2,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { WorldbuildingAnalysisResponse } from "@/lib/api/worldbuilding";
import { useWorldbuildingAnalyze, useWorldbuildingApply } from "@/lib/hooks/useWorldbuilding";
import {
  ConnectionCard,
  ConsistencyCard,
  GapCard,
  groupByCategory,
} from "./WorldbuildingAnalysisCards";

// --- Types ---

type AnalysisTab = "gaps" | "connections" | "consistency";
type AnalysisViewState = "idle" | "loading" | "results" | "error";

interface WorldbuildingAnalysisPanelProps {
  novelId: string;
  onClose: () => void;
}

// --- Severity sort order ---

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  major: 1,
  minor: 2,
  info: 3,
};

// --- Tab config ---

const TAB_CONFIG: { key: AnalysisTab; icon: typeof Sparkles }[] = [
  { key: "gaps", icon: Search },
  { key: "connections", icon: Link2 },
  { key: "consistency", icon: AlertTriangle },
];

export function WorldbuildingAnalysisPanel({ novelId, onClose }: WorldbuildingAnalysisPanelProps) {
  const t = useTranslations("studio");

  const [state, setState] = useState<AnalysisViewState>("idle");
  const [analysis, setAnalysis] = useState<WorldbuildingAnalysisResponse | null>(null);
  const [activeTab, setActiveTab] = useState<AnalysisTab>("gaps");
  const [selectedConnectionIndices, setSelectedConnectionIndices] = useState<Set<number>>(
    new Set(),
  );
  const [error, setError] = useState<Error | null>(null);
  const [applyMessage, setApplyMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const analyzeMutation = useWorldbuildingAnalyze(novelId);
  const applyMutation = useWorldbuildingApply(novelId);

  // --- Run analysis ---

  const runAnalysis = useCallback(
    async (refresh = false) => {
      setState("loading");
      setError(null);
      setApplyMessage(null);

      try {
        const result = await analyzeMutation.mutateAsync({ refresh });
        setAnalysis(result);
        setSelectedConnectionIndices(new Set());
        setState("results");
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setState("error");
      }
    },
    [analyzeMutation],
  );

  // Auto-trigger on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount
  useEffect(() => {
    if (state !== "idle") return;
    void runAnalysis(false);
  }, []);

  // --- Connection selection ---

  function toggleConnection(index: number) {
    setSelectedConnectionIndices((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }

  function selectAllConnections() {
    if (!analysis) return;
    setSelectedConnectionIndices(
      new Set(analysis.connection_suggestions.map((c) => c.finding_index)),
    );
  }

  function selectNoConnections() {
    setSelectedConnectionIndices(new Set());
  }

  // --- Apply connections ---

  async function applySelectedConnections() {
    if (!analysis) return;

    try {
      const result = await applyMutation.mutateAsync({
        finding_indices: Array.from(selectedConnectionIndices),
        analysis,
      });

      if (result.success) {
        setApplyMessage({
          type: "success",
          text:
            t("worldbuilding.applied", { count: result.created_count }) ||
            `Applied ${result.created_count} connections`,
        });
        setSelectedConnectionIndices(new Set());
        await runAnalysis(true);
      } else {
        setApplyMessage({
          type: "error",
          text: t("worldbuilding.failed") || `Failed to apply: ${result.errors.join(", ")}`,
        });
      }
    } catch (err) {
      setApplyMessage({
        type: "error",
        text: err instanceof Error ? err.message : t("worldbuilding.failed") || "Apply failed",
      });
    }
  }

  // --- Derived data ---

  const sortedGaps = analysis
    ? [...analysis.gap_findings].sort(
        (a, b) => (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99),
      )
    : [];

  const connections = analysis?.connection_suggestions ?? [];
  const consistencyIssues = analysis?.consistency_issues ?? [];
  const groupedConsistency = groupByCategory(consistencyIssues);

  const hasNoFindings =
    analysis &&
    analysis.gap_findings.length === 0 &&
    analysis.connection_suggestions.length === 0 &&
    analysis.consistency_issues.length === 0;

  // --- Render ---

  return (
    <div className="flex flex-col h-full border-l border-border bg-background">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <Sparkles className="w-5 h-5 text-purple-500 flex-shrink-0" />
            <h3 className="font-medium truncate">
              {t("worldbuilding.analysisTitle") || "Worldbuilding Analysis"}
            </h3>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {state === "results" && (
            <button
              type="button"
              onClick={() => void runAnalysis(true)}
              disabled={analyzeMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors disabled:opacity-50"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${analyzeMutation.isPending ? "animate-spin" : ""}`}
              />
              {t("worldbuilding.refresh") || "Refresh"}
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Score header */}
      {state === "results" && analysis && (
        <div className="flex items-start gap-4 p-4 border-b border-border bg-muted/30">
          <div className="flex-shrink-0 flex flex-col items-center">
            <div className="text-2xl font-bold text-purple-500">
              {analysis.worldbuilding_score.toFixed(2)}
            </div>
            <div className="text-xs text-muted-foreground">
              {t("worldbuilding.score") || "Score"}
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <div className="w-full h-2 bg-muted rounded-full overflow-hidden mb-2">
              <div
                className="h-full bg-purple-500 rounded-full transition-all duration-500"
                style={{ width: `${Math.round(analysis.worldbuilding_score * 100)}%` }}
              />
            </div>
            <p className="text-sm text-muted-foreground line-clamp-2">
              {analysis.overall_assessment}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {t("worldbuilding.entityCount", { count: analysis.entity_count }) ||
                `${analysis.entity_count} entities analyzed`}
            </p>
          </div>
        </div>
      )}

      {/* Apply message banner */}
      {applyMessage && (
        <div
          className={`px-4 py-2 text-sm border-b ${
            applyMessage.type === "success"
              ? "bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-900/50"
              : "bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-900/50"
          }`}
        >
          {applyMessage.text}
        </div>
      )}

      {/* Tabs */}
      {state === "results" && !hasNoFindings && (
        <div className="flex border-b border-border bg-card">
          {TAB_CONFIG.map(({ key, icon: TabIcon }) => {
            const count =
              key === "gaps"
                ? (analysis?.gap_findings.length ?? 0)
                : key === "connections"
                  ? (analysis?.connection_suggestions.length ?? 0)
                  : (analysis?.consistency_issues.length ?? 0);

            return (
              <button
                key={key}
                type="button"
                onClick={() => setActiveTab(key)}
                className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === key
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                <TabIcon className="w-4 h-4" />
                {t(`worldbuilding.${key}`) || key.charAt(0).toUpperCase() + key.slice(1)}
                <span
                  className={`text-xs px-1.5 py-0.5 rounded ${activeTab === key ? "bg-primary/10" : "bg-muted"}`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          {/* Loading state */}
          {state === "loading" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="relative mb-6">
                <div className="w-16 h-16 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
                </div>
              </div>
              <p className="text-lg font-medium mb-2">
                {t("worldbuilding.analyzing") || "Analyzing worldbuilding..."}
              </p>
              <p className="text-sm text-muted-foreground">
                {t("worldbuilding.analyzingDesc") ||
                  "The AI is reviewing your world for gaps, connections, and consistency..."}
              </p>
              <div className="w-64 h-1.5 bg-muted rounded-full overflow-hidden mt-6">
                <div className="h-full bg-purple-500 animate-pulse" style={{ width: "60%" }} />
              </div>
            </div>
          )}

          {/* Error state */}
          {state === "error" && error && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
                <AlertTriangle className="w-6 h-6 text-red-500" />
              </div>
              <p className="text-lg font-medium mb-1">
                {t("worldbuilding.error") || "Analysis failed"}
              </p>
              <p className="text-sm text-muted-foreground mb-4">{error.message}</p>
              <button
                type="button"
                onClick={() => void runAnalysis(false)}
                className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                {t("worldbuilding.retry") || "Retry"}
              </button>
            </div>
          )}

          {/* No findings state */}
          {state === "results" && hasNoFindings && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-4">
                <Check className="w-6 h-6 text-green-500" />
              </div>
              <p className="text-lg font-medium mb-1">
                {t("worldbuilding.noIssues") || "No issues found!"}
              </p>
              <p className="text-sm text-muted-foreground">
                {t("worldbuilding.noIssuesDesc") ||
                  "Your worldbuilding looks comprehensive and consistent."}
              </p>
            </div>
          )}

          {/* Tab: Gaps */}
          {state === "results" && activeTab === "gaps" && sortedGaps.length > 0 && (
            <div className="space-y-3">
              {sortedGaps.map((gap) => (
                <GapCard
                  key={`${gap.entity_id ?? "none"}-${gap.gap_type}-${gap.field_key ?? "body"}`}
                  gap={gap}
                  t={t}
                />
              ))}
            </div>
          )}

          {/* Tab: Connections */}
          {state === "results" && activeTab === "connections" && connections.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
                <span className="text-sm text-muted-foreground">
                  {t("worldbuilding.selectedCount", {
                    count: selectedConnectionIndices.size,
                    total: connections.length,
                  }) || `${selectedConnectionIndices.size} of ${connections.length} selected`}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={selectAllConnections}
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    {t("kb.selectAll") || "Select all"}
                  </button>
                  <span className="text-muted-foreground">|</span>
                  <button
                    type="button"
                    onClick={selectNoConnections}
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    {t("kb.selectNone") || "Select none"}
                  </button>
                </div>
              </div>
              {connections.map((conn) => (
                <ConnectionCard
                  key={conn.finding_index}
                  connection={conn}
                  isSelected={selectedConnectionIndices.has(conn.finding_index)}
                  onToggle={() => toggleConnection(conn.finding_index)}
                  t={t}
                />
              ))}
            </div>
          )}

          {/* Tab: Consistency */}
          {state === "results" && activeTab === "consistency" && consistencyIssues.length > 0 && (
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
          )}
        </div>
      </div>

      {/* Footer — Apply button for connections tab */}
      {state === "results" && activeTab === "connections" && connections.length > 0 && (
        <div className="flex items-center justify-between p-4 border-t border-border bg-card">
          <button
            type="button"
            onClick={onClose}
            className="flex items-center gap-2 px-4 py-2 border border-border rounded-md hover:bg-muted transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            {t("worldbuilding.close") || "Close"}
          </button>
          <button
            type="button"
            onClick={() => void applySelectedConnections()}
            disabled={selectedConnectionIndices.size === 0 || applyMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50 text-sm"
          >
            {applyMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Check className="w-4 h-4" />
            )}
            {applyMutation.isPending
              ? t("worldbuilding.applying") || "Applying..."
              : t("worldbuilding.apply", { count: selectedConnectionIndices.size }) ||
                `Apply Selected (${selectedConnectionIndices.size})`}
          </button>
        </div>
      )}
    </div>
  );
}
