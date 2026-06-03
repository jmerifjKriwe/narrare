"use client";

/**
 * POVPanel — collapsible side panel for POV Analysis (ANAL-004).
 *
 * Shows POV distribution chart, scene map with confidence badges,
 * issues list with severity/type icons, and summary stats.
 * Follows ReadabilityPanel layout (400px wide, border-left).
 */

import { ArrowLeft, Eye, Info, Loader2, RefreshCw, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { POVResult } from "@/lib/api/analysis";
import { usePOVAnalysis } from "@/lib/hooks/usePOV";
import { POVResultsContent } from "./_components/POVResultsContent";

// --- Types ---

interface POVPanelProps {
  novelId: string;
  chapterIds: string[];
  onClose: () => void;
}

// --- Component ---

export function POVPanel({ novelId, chapterIds, onClose }: POVPanelProps) {
  const t = useTranslations("analysis");

  const [viewState, setViewState] = useState<"idle" | "loading" | "results" | "error">("idle");
  const [result, setResult] = useState<POVResult | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const analyzeMutation = usePOVAnalysis(novelId);

  // --- Run analysis ---

  const runAnalysis = useCallback(
    async (_refresh = false) => {
      if (chapterIds.length === 0) return;
      setViewState("loading");
      setError(null);

      try {
        const res = await analyzeMutation.mutateAsync({
          chapter_ids: chapterIds,
        });
        setResult(res);
        setViewState("results");
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setViewState("error");
      }
    },
    [chapterIds, analyzeMutation],
  );

  // Auto-trigger on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount
  useEffect(() => {
    if (viewState !== "idle") return;
    void runAnalysis(false);
  }, []);

  // --- Derived ---

  const distributionEntries = result
    ? Object.entries(result.pov_distribution).sort(([, a], [, b]) => b - a)
    : [];

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
            <Eye className="w-5 h-5 text-indigo-500 flex-shrink-0" />
            <h3 className="font-medium truncate">{t("pov.title")}</h3>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {viewState === "results" && (
            <button
              type="button"
              onClick={() => void runAnalysis(true)}
              disabled={analyzeMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors disabled:opacity-50"
              aria-label={t("refresh")}
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${analyzeMutation.isPending ? "animate-spin" : ""}`}
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

      {/* Info banner */}
      <div className="px-4 py-1.5 border-b border-border bg-muted/30">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5 flex-shrink-0" />
          {t("pov.description")}
        </p>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          {/* Loading state */}
          {viewState === "loading" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="relative mb-6">
                <div className="w-16 h-16 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
                </div>
              </div>
              <p className="text-lg font-medium mb-2">{t("pov.analyzing")}</p>
            </div>
          )}

          {/* Error state */}
          {viewState === "error" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
                <Info className="w-6 h-6 text-red-500" />
              </div>
              <p className="text-lg font-medium mb-1">{t("pov.analysisFailed")}</p>
              <p className="text-sm text-muted-foreground mb-4">{error?.message}</p>
              <button
                type="button"
                onClick={() => void runAnalysis(false)}
                className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                {t("pov.retry")}
              </button>
            </div>
          )}

          {/* Results */}
          {viewState === "results" && result && (
            <POVResultsContent result={result} distributionEntries={distributionEntries} t={t} />
          )}
        </div>
      </div>
    </div>
  );
}
