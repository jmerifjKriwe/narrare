"use client";

/**
 * ConsistencyPanel — collapsible side panel for Consistency Checker (CONS-001).
 *
 * Shows severity summary badges, overall assessment, and filterable issue cards.
 * Follows BetaReaderPanel layout (400px wide, border-left).
 */

import { AlertTriangle, ArrowLeft, Info, Loader2, RefreshCw, Shield, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { ConsistencyResponse } from "@/lib/api/analysis";
import { useConsistencyCheck } from "@/lib/hooks/useConsistency";
import { useEditorStore } from "@/lib/stores/editorStore";
import { ConsistencyIssueList } from "./ConsistencyIssueList";

// --- Types ---

interface ConsistencyPanelProps {
  novelId: string;
  chapterIds: string[];
  onClose: () => void;
}

// --- Severity badge ---

function SeverityBadge({
  count,
  label,
  colorClass,
}: {
  count: number;
  label: string;
  colorClass: string;
}) {
  return (
    <div
      className={`flex flex-col items-center gap-1 px-4 py-2 rounded-lg border border-border ${colorClass}`}
    >
      <span className="text-xl font-bold">{count}</span>
      <span className="text-xs font-medium">{label}</span>
    </div>
  );
}

// --- Component ---

export function ConsistencyPanel({ novelId, chapterIds, onClose }: ConsistencyPanelProps) {
  const t = useTranslations("analysis");

  const [viewState, setViewState] = useState<"idle" | "loading" | "results" | "error">("idle");
  const [result, setResult] = useState<ConsistencyResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const checkMutation = useConsistencyCheck(novelId);
  const setConsistencyResult = useEditorStore((s) => s.setConsistencyResult);
  const setConsistencyLoading = useEditorStore((s) => s.setConsistencyLoading);

  // --- Run consistency check ---

  const runCheck = useCallback(async () => {
    if (chapterIds.length === 0) return;
    setViewState("loading");
    setConsistencyLoading(true);
    setError(null);

    try {
      const res = await checkMutation.mutateAsync({
        chapter_ids: chapterIds,
        check_types: ["character", "timeline", "world", "plot"],
        include_kb: true,
      });
      setResult(res);
      setConsistencyResult(res);
      setViewState("results");
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setViewState("error");
    } finally {
      setConsistencyLoading(false);
    }
  }, [chapterIds, checkMutation, setConsistencyResult, setConsistencyLoading]);

  // Auto-trigger on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount
  useEffect(() => {
    if (viewState !== "idle") return;
    void runCheck();
  }, []);

  // --- i18n adapter ---

  const tFn = (key: string, params?: Record<string, unknown>) => {
    return t(key as Parameters<typeof t>[0], params as Parameters<typeof t>[1]) as string;
  };

  // --- Render ---

  return (
    <div className="flex flex-col h-full border-l border-border bg-background w-[400px] min-w-[400px]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
            aria-label={t("close")}
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <Shield className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0" />
            <h3 className="font-medium truncate">{t("consistency.title")}</h3>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {viewState === "results" && (
            <button
              type="button"
              onClick={() => void runCheck()}
              disabled={checkMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors disabled:opacity-50"
              aria-label={t("refresh")}
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${checkMutation.isPending ? "animate-spin" : ""}`}
              />
              {t("refresh")}
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
            aria-label={t("close")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* AI disclaimer */}
      <div className="px-4 py-1.5 border-b border-border bg-muted/30">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5 flex-shrink-0" />
          {t("consistency.aiDisclaimer")}
        </p>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          {/* Loading state */}
          {viewState === "loading" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="relative mb-6">
                <div className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-green-600 animate-spin" />
                </div>
              </div>
              <p className="text-lg font-medium mb-2">{t("consistency.loading")}</p>
              <p className="text-sm text-muted-foreground">{t("consistency.loadingSubtext")}</p>
            </div>
          )}

          {/* Error state */}
          {viewState === "error" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
                <AlertTriangle className="w-6 h-6 text-red-500" />
              </div>
              <p className="text-lg font-medium mb-1">{t("error")}</p>
              <p className="text-sm text-muted-foreground mb-4">{error?.message}</p>
              <button
                type="button"
                onClick={() => void runCheck()}
                className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                {t("retry")}
              </button>
            </div>
          )}

          {/* Results */}
          {viewState === "results" && result && (
            <>
              {/* Summary badges */}
              <section className="flex items-center justify-center gap-3">
                <SeverityBadge
                  count={result.error_count}
                  label={t("consistency.severity.error")}
                  colorClass="bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400"
                />
                <SeverityBadge
                  count={result.warning_count}
                  label={t("consistency.severity.warning")}
                  colorClass="bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400"
                />
                <SeverityBadge
                  count={result.info_count}
                  label={t("consistency.severity.info")}
                  colorClass="bg-blue-50 dark:bg-blue-950/20 text-blue-700 dark:text-blue-400"
                />
              </section>

              {/* Overall assessment */}
              <section>
                <h4 className="text-sm font-medium mb-2">{t("consistency.overallAssessment")}</h4>
                <p className="text-sm text-muted-foreground">{result.overall_assessment}</p>
              </section>

              {/* Issues list with filtering */}
              <section>
                <h4 className="text-sm font-medium mb-3">
                  {t("consistency.issues", { count: result.total_issues })}
                </h4>
                <ConsistencyIssueList issues={result.issues} t={tFn} />
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
