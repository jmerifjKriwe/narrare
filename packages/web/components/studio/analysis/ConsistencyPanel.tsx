"use client";

/**
 * ConsistencyPanel — collapsible side panel for Consistency Checker (CONS-001).
 *
 * Shows severity summary badges, overall assessment, and filterable issue cards.
 * Follows BetaReaderPanel layout (400px wide, border-left).
 */

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ConsistencyResponse } from "@/lib/api/analysis";
import { useConsistencyCheck } from "@/lib/hooks/useConsistency";
import { useEditorStore } from "@/lib/stores/editorStore";
import { ConsistencyPanelHeader } from "./ConsistencyPanelHeader";
import {
  ConsistencyErrorState,
  ConsistencyLoadingState,
  ConsistencyResults,
  ConsistencyScopeSelector,
} from "./ConsistencyPanelSections";

// --- Types ---

/** Scope controls which chapters are included in the check. */
type Scope = "current" | "selected" | "all";

interface ConsistencyPanelProps {
  novelId: string;
  chapterIds: string[];
  onClose: () => void;
}

export function ConsistencyPanel({ novelId, chapterIds, onClose }: ConsistencyPanelProps) {
  const t = useTranslations("analysis");

  const [scope, setScope] = useState<Scope>("selected");
  const [viewState, setViewState] = useState<"idle" | "loading" | "results" | "error">("idle");
  const [result, setResult] = useState<ConsistencyResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const checkMutation = useConsistencyCheck(novelId);
  const setConsistencyResult = useEditorStore((s) => s.setConsistencyResult);
  const setConsistencyLoading = useEditorStore((s) => s.setConsistencyLoading);
  const activeChapterId = useEditorStore((s) => s.activeChapterId);

  // --- Scope → chapter IDs mapping ---

  const getChapterIds = useCallback((): string[] => {
    if (scope === "current") return activeChapterId ? [activeChapterId] : chapterIds.slice(0, 1);
    if (scope === "all") return [];
    return chapterIds;
  }, [scope, activeChapterId, chapterIds]);

  // --- Run consistency check ---

  const runCheck = useCallback(async () => {
    const ids = getChapterIds();
    // Allow empty ids only for "all" scope (backend fetches all chapters)
    if (ids.length === 0 && scope !== "all") return;
    setViewState("loading");
    setConsistencyLoading(true);
    setError(null);

    try {
      const res = await checkMutation.mutateAsync({
        chapter_ids: ids,
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
  }, [getChapterIds, scope, checkMutation, setConsistencyResult, setConsistencyLoading]);

  // Auto-trigger on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount
  useEffect(() => {
    if (viewState !== "idle") return;
    void runCheck();
  }, []);

  // --- Elapsed timer for loading progress ---
  useEffect(() => {
    if (viewState !== "loading") {
      setElapsed(0);
      return;
    }
    elapsedRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => {
      if (elapsedRef.current) clearInterval(elapsedRef.current);
    };
  }, [viewState]);

  const loadingStep =
    elapsed < 5
      ? "collecting"
      : elapsed < 15
        ? "loading"
        : elapsed < 35
          ? "analyzing"
          : "finishing";

  // --- i18n adapter ---

  const tFn = (key: string, params?: Record<string, unknown>) => {
    return t(key as Parameters<typeof t>[0], params as Parameters<typeof t>[1]) as string;
  };

  // --- Render ---

  return (
    <div className="flex flex-col h-full border-l border-border bg-background w-[400px] min-w-[400px]">
      <ConsistencyPanelHeader
        viewState={viewState}
        isPending={checkMutation.isPending}
        onClose={onClose}
        onRefresh={() => void runCheck()}
        t={t}
      />

      {/* Scope selector */}
      {viewState !== "loading" && (
        <ConsistencyScopeSelector scope={scope} onScopeChange={setScope} t={t} />
      )}

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          {/* Loading state */}
          {viewState === "loading" && (
            <ConsistencyLoadingState elapsed={elapsed} loadingStep={loadingStep} t={tFn} />
          )}

          {/* Error state */}
          {viewState === "error" && (
            <ConsistencyErrorState error={error} onRetry={() => void runCheck()} t={t} />
          )}

          {/* Results */}
          {viewState === "results" && result && <ConsistencyResults result={result} t={tFn} />}
        </div>
      </div>
    </div>
  );
}
