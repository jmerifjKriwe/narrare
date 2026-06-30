"use client";

/**
 * ConsistencyPanel — collapsible side panel for Consistency Checker (CONS-001).
 *
 * Shows severity summary badges, overall assessment, and filterable issue cards.
 * Follows BetaReaderPanel layout (400px wide, border-left).
 *
 * Uses useConsistencyStream for SSE-based lifecycle with progressive stage
 * updates and per-issue accumulation, replacing the older useAIOperation
 * + analysisApi.consistencyCheck mutation pattern.
 */

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ConsistencyCheckRequest } from "@/lib/api/consistency-stream";
import { useConsistencyStream } from "@/lib/hooks/useConsistencyStream";
import { useEditorStore } from "@/lib/stores/editorStore";
import { ConsistencyPanelHeader } from "./ConsistencyPanelHeader";
import {
  ConsistencyErrorState,
  ConsistencyLoadingState,
  ConsistencyResults,
  ConsistencyScopeSelector,
} from "./ConsistencyPanelSections";
import { getChapterIdsForScope, type Scope, useElapsedTimer } from "./consistencyPanelUtils";

// --- Types ---

interface ConsistencyPanelProps {
  novelId: string;
  chapterIds: string[];
  onClose: () => void;
}

export function ConsistencyPanel({ novelId, chapterIds, onClose }: ConsistencyPanelProps) {
  const t = useTranslations("analysis");
  const tStudio = useTranslations("studio");

  const [scope, setScope] = useState<Scope>("selected");
  const scopeRef = useRef(scope);
  scopeRef.current = scope;

  const setConsistencyResult = useEditorStore((s) => s.setConsistencyResult);
  const setConsistencyLoading = useEditorStore((s) => s.setConsistencyLoading);
  const activeChapterId = useEditorStore((s) => s.activeChapterId);

  // --- Streaming lifecycle (useConsistencyStream wraps useAIOperation internally) ---

  const {
    run,
    progress,
    result,
    error,
    cancel,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  } = useConsistencyStream();

  const viewState: "idle" | "loading" | "results" | "error" = isConnectionLost
    ? "error"
    : isLoading || isStreaming
      ? "loading"
      : isError
        ? "error"
        : isComplete
          ? "results"
          : "idle";

  const isPending = isLoading || isStreaming;

  // --- Elapsed timer ---

  const { elapsed, loadingStep } = useElapsedTimer(isPending);

  // --- Run / Cancel ---

  const runCheck = useCallback(() => {
    setConsistencyLoading(true);
    const currentScope = scopeRef.current;
    const ids = getChapterIdsForScope(currentScope, activeChapterId, chapterIds);
    const request: ConsistencyCheckRequest = {
      chapter_ids: ids.length > 0 ? ids : undefined,
      check_types: ["character", "timeline", "world", "plot"],
      include_kb: true,
    };
    run(novelId, request);
  }, [novelId, chapterIds, activeChapterId, run, setConsistencyLoading]);

  // Sync loading state to store
  useEffect(() => {
    setConsistencyLoading(isPending);
  }, [isPending, setConsistencyLoading]);

  // Sync result to store when stream completes
  useEffect(() => {
    if (result) {
      setConsistencyResult(result);
    }
  }, [result, setConsistencyResult]);

  // Auto-trigger on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount
  useEffect(() => {
    if (viewState !== "idle") return;
    runCheck();
  }, []);

  // --- i18n adapter ---

  const tFn = (key: string, params?: Record<string, unknown>) => {
    return t(key as Parameters<typeof t>[0], params as Parameters<typeof t>[1]) as string;
  };

  // --- Error message ---

  const errorMessage = error?.userMessage || t("error");

  // --- Render ---

  return (
    <div className="flex flex-col h-full border-l border-border bg-background w-[400px] min-w-[400px]">
      <ConsistencyPanelHeader
        viewState={viewState}
        isPending={isPending}
        onClose={onClose}
        onRefresh={() => runCheck()}
        onCancel={isPending ? cancel : undefined}
        t={t}
        tStudio={tStudio}
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
            <ConsistencyLoadingState
              elapsed={elapsed}
              loadingStep={loadingStep}
              progress={progress}
              t={tFn}
            />
          )}

          {/* Error state */}
          {viewState === "error" && (
            <ConsistencyErrorState
              errorMessage={errorMessage}
              isConnectionLost={isConnectionLost}
              onRetry={() => runCheck()}
              t={t}
              tStudio={tStudio}
            />
          )}

          {/* Results */}
          {viewState === "results" && result && <ConsistencyResults result={result} t={tFn} />}
        </div>
      </div>
    </div>
  );
}
