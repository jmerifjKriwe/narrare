"use client";

/**
 * ConsistencyPanel — collapsible side panel for Consistency Checker (CONS-001).
 *
 * Shows severity summary badges, overall assessment, and filterable issue cards.
 * Follows BetaReaderPanel layout (400px wide, border-left).
 *
 * Uses useAIOperation for lifecycle management with structured error mapping
 * and cancel support (§16 AI-Interaction Standards).
 */

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import { analysisApi, type ConsistencyResponse } from "@/lib/api/analysis";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { useEditorStore } from "@/lib/stores/editorStore";
import { ConsistencyPanelHeader } from "./ConsistencyPanelHeader";
import {
  ConsistencyErrorState,
  ConsistencyLoadingState,
  ConsistencyResults,
  ConsistencyScopeSelector,
} from "./ConsistencyPanelSections";
import {
  getChapterIdsForScope,
  getConsistencyErrorMessage,
  type Scope,
  useElapsedTimer,
} from "./consistencyPanelUtils";

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
  const [result, setResult] = useState<ConsistencyResponse | null>(null);
  const scopeRef = useRef(scope);
  scopeRef.current = scope;

  const setConsistencyResult = useEditorStore((s) => s.setConsistencyResult);
  const setConsistencyLoading = useEditorStore((s) => s.setConsistencyLoading);
  const activeChapterId = useEditorStore((s) => s.activeChapterId);

  // --- AI Operation lifecycle ---

  const aiOp = useAIOperation<ConsistencyResponse>({
    execute: async (signal) => {
      const currentScope = scopeRef.current;
      const ids = getChapterIdsForScope(currentScope, activeChapterId, chapterIds);
      if (ids.length === 0 && currentScope !== "all") {
        throw new Error("No chapters selected");
      }
      return analysisApi.consistencyCheck(
        novelId,
        {
          chapter_ids: ids,
          check_types: ["character", "timeline", "world", "plot"],
          include_kb: true,
        },
        signal,
      );
    },
    errorMapper: (error) => {
      const mapped = mapSSEError(error);
      if (mapped) return mapped;
      // mapSSEError returns null for aborts — propagate that
      return null;
    },
    onSuccess: (res) => {
      setResult(res);
      setConsistencyResult(res);
    },
    onError: () => {
      setResult(null);
    },
    connectionLossTimeout: 30_000,
  });

  const viewState: "idle" | "loading" | "results" | "error" = aiOp.isConnectionLost
    ? "error"
    : aiOp.isLoading || aiOp.isStreaming
      ? "loading"
      : aiOp.isError
        ? "error"
        : aiOp.isComplete
          ? "results"
          : "idle";

  const structuredError = aiOp.state.error;

  // --- Elapsed timer ---

  const { elapsed, loadingStep } = useElapsedTimer(aiOp.isLoading || aiOp.isStreaming);

  // --- Run / Cancel ---

  const runCheck = useCallback(() => {
    setConsistencyLoading(true);
    aiOp.start();
  }, [aiOp, setConsistencyLoading]);

  // Sync loading state to store
  useEffect(() => {
    setConsistencyLoading(aiOp.isLoading || aiOp.isStreaming);
  }, [aiOp.isLoading, aiOp.isStreaming, setConsistencyLoading]);

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

  const errorMessage = getConsistencyErrorMessage(structuredError, t, tStudio);

  // --- Render ---

  return (
    <div className="flex flex-col h-full border-l border-border bg-background w-[400px] min-w-[400px]">
      <ConsistencyPanelHeader
        viewState={viewState}
        isPending={aiOp.isLoading || aiOp.isStreaming}
        onClose={onClose}
        onRefresh={() => runCheck()}
        onCancel={aiOp.isLoading || aiOp.isStreaming ? aiOp.cancel : undefined}
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
            <ConsistencyLoadingState elapsed={elapsed} loadingStep={loadingStep} t={tFn} />
          )}

          {/* Error state */}
          {viewState === "error" && (
            <ConsistencyErrorState
              errorMessage={errorMessage}
              isConnectionLost={aiOp.isConnectionLost}
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
