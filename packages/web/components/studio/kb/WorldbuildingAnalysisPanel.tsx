"use client";

/**
 * WorldbuildingAnalysisPanel — AI-powered worldbuilding analysis.
 *
 * Shows analysis results with 3 tabs (Gaps, Connections, Consistency)
 * plus a score header. Auto-triggers analysis on mount.
 * Sub-components: AnalysisLoading, AnalysisError, AnalysisScoreHeader, AnalysisTabs.
 *
 * §16 compliance: AbortController cancel, useConnectionLost, studio.aiActions.* labels.
 */

import { ArrowLeft, Check, Link2, Loader2, RefreshCw, Search, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { ConnectionLostBanner } from "@/components/ui/connection-lost-banner";
import type { WorldbuildingAnalysisResponse } from "@/lib/api/worldbuilding";
import { useConnectionLost } from "@/lib/hooks/use-connection-lost";
import { useWorldbuildingAnalyze, useWorldbuildingApply } from "@/lib/hooks/useWorldbuilding";
import { AnalysisError } from "./AnalysisError";
import { AnalysisLoading } from "./AnalysisLoading";
import { AnalysisScoreHeader } from "./AnalysisScoreHeader";
import { AnalysisTabs } from "./AnalysisTabs";

type AnalysisTab = "gaps" | "connections" | "consistency";
type AnalysisViewState = "idle" | "loading" | "results" | "error";

interface WorldbuildingAnalysisPanelProps {
  novelId: string;
  onClose: () => void;
}

const TAB_CONFIG: { key: AnalysisTab; icon: typeof Sparkles }[] = [
  { key: "gaps", icon: Search },
  { key: "connections", icon: Link2 },
  { key: "consistency", icon: Sparkles },
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
  const {
    isConnectionLost,
    markConnectionLost,
    retry: retryConnection,
  } = useConnectionLost({ onRetry: () => void runAnalysis(false) });

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
        if (err instanceof DOMException && err.name === "AbortError") return;
        markConnectionLost();
        setError(err instanceof Error ? err : new Error(String(err)));
        setState("error");
      }
    },
    [analyzeMutation, markConnectionLost],
  );

  // biome-ignore lint/correctness/useExhaustiveDependencies: mount-only
  useEffect(() => {
    if (state === "idle") void runAnalysis(false);
  }, []);

  const toggleConnection = useCallback((index: number) => {
    setSelectedConnectionIndices((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }, []);

  const handleCancel = useCallback(() => {
    analyzeMutation.abort();
    setState("idle");
  }, [analyzeMutation]);

  const applySelectedConnections = useCallback(async () => {
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
          text: t("worldbuilding.failed") || `Failed: ${result.errors.join(", ")}`,
        });
      }
    } catch (err) {
      setApplyMessage({
        type: "error",
        text: err instanceof Error ? err.message : t("worldbuilding.failed") || "Apply failed",
      });
    }
  }, [analysis, selectedConnectionIndices, applyMutation, t, runAnalysis]);

  const hasNoFindings =
    analysis &&
    analysis.gap_findings.length === 0 &&
    analysis.connection_suggestions.length === 0 &&
    analysis.consistency_issues.length === 0;

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
          <Sparkles className="w-5 h-5 text-purple-500 flex-shrink-0" />
          <h3 className="font-medium truncate">
            {t("worldbuilding.analysisTitle") || "Worldbuilding Analysis"}
          </h3>
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
      {isConnectionLost && (
        <div className="p-4 pb-0">
          <ConnectionLostBanner onRetry={retryConnection} />
        </div>
      )}
      {state === "results" && analysis && <AnalysisScoreHeader analysis={analysis} />}
      {applyMessage && (
        <div
          className={`px-4 py-2 text-sm border-b ${applyMessage.type === "success" ? "bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-900/50" : "bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-900/50"}`}
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
                className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm font-medium transition-colors border-b-2 ${activeTab === key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
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

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          {state === "loading" && <AnalysisLoading onCancel={handleCancel} />}
          {state === "error" && error && (
            <AnalysisError message={error.message} onRetry={() => void runAnalysis(false)} />
          )}
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
          {state === "results" && analysis && !hasNoFindings && (
            <AnalysisTabs
              activeTab={activeTab}
              analysis={analysis}
              selectedConnectionIndices={selectedConnectionIndices}
              onToggleConnection={toggleConnection}
              onSelectAll={() =>
                setSelectedConnectionIndices(
                  new Set(analysis.connection_suggestions.map((c) => c.finding_index)),
                )
              }
              onSelectNone={() => setSelectedConnectionIndices(new Set())}
            />
          )}
        </div>
      </div>

      {/* Footer — Apply button for connections tab */}
      {state === "results" &&
        activeTab === "connections" &&
        (analysis?.connection_suggestions.length ?? 0) > 0 && (
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
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {t("worldbuilding.applying") || "Applying..."}
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  {t("worldbuilding.apply", { count: selectedConnectionIndices.size }) ||
                    `Apply Selected (${selectedConnectionIndices.size})`}
                </>
              )}
            </button>
          </div>
        )}
    </div>
  );
}
