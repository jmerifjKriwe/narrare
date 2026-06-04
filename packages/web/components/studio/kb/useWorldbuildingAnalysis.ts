"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { WorldbuildingAnalysisResponse } from "@/lib/api/worldbuilding";
import { useConnectionLost } from "@/lib/hooks/use-connection-lost";
import { useWorldbuildingAnalyze, useWorldbuildingApply } from "@/lib/hooks/useWorldbuilding";

export type AnalysisTab = "gaps" | "connections" | "consistency";
export type AnalysisViewState = "idle" | "loading" | "results" | "error";

interface ApplyMessage {
  type: "success" | "error";
  text: string;
}

export function useWorldbuildingAnalysis(novelId: string) {
  const t = useTranslations("studio");
  const [state, setState] = useState<AnalysisViewState>("idle");
  const [analysis, setAnalysis] = useState<WorldbuildingAnalysisResponse | null>(null);
  const [activeTab, setActiveTab] = useState<AnalysisTab>("gaps");
  const [selectedConnectionIndices, setSelectedConnectionIndices] = useState<Set<number>>(
    new Set(),
  );
  const [error, setError] = useState<Error | null>(null);
  const [applyMessage, setApplyMessage] = useState<ApplyMessage | null>(null);

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

  return {
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
  };
}
