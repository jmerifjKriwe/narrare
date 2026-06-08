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

import { ArrowLeft, Check, Loader2, RefreshCw, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { ConnectionLostBanner } from "@/components/ui/connection-lost-banner";
import { AnalysisError } from "./AnalysisError";
import { AnalysisLoading } from "./AnalysisLoading";
import { AnalysisScoreHeader } from "./AnalysisScoreHeader";
import { AnalysisTabs } from "./AnalysisTabs";
import { useWorldbuildingAnalysis } from "./useWorldbuildingAnalysis";
import { WorldbuildingAnalysisTabBar } from "./WorldbuildingAnalysisTabBar";

interface WorldbuildingAnalysisPanelProps {
  novelId: string;
  onClose: () => void;
}

export function WorldbuildingAnalysisPanel({ novelId, onClose }: WorldbuildingAnalysisPanelProps) {
  const t = useTranslations("studio");
  const {
    state,
    analysis,
    activeTab,
    setActiveTab,
    selectedConnectionIndices,
    setSelectedConnectionIndices,
    error,
    applyMessage,
    analyzeMutation,
    applyMutation,
    isConnectionLost,
    retryConnection,
    runAnalysis,
    toggleConnection,
    handleCancel,
    applySelectedConnections,
    hasNoFindings,
  } = useWorldbuildingAnalysis(novelId);

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
        <WorldbuildingAnalysisTabBar
          activeTab={activeTab}
          analysis={analysis}
          onActiveTabChange={setActiveTab}
        />
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          {state === "loading" && <AnalysisLoading onCancel={handleCancel} />}
          {state === "error" && error && (
            <AnalysisError
              message={
                "userMessage" in error
                  ? (error as { userMessage: string }).userMessage
                  : error["message"]
              }
              onRetry={() => void runAnalysis(false)}
            />
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
