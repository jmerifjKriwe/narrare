"use client";

/**
 * ConsistencyCheckPanel — KB consistency check results.
 *
 * Auto-triggers check on mount. Shows issues grouped by category.
 * Uses useAIOperation for lifecycle management (no manual AbortController,
 * built-in connection-loss detection, structured error mapping).
 *
 * §16 compliance: studio.aiActions.* labels, actionable error messages.
 *
 * @module ConsistencyCheckPanel
 */

import { ArrowLeft, RefreshCw, ShieldCheck, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect } from "react";
import { ConnectionLostBanner } from "@/components/ui/connection-lost-banner";
import { mapRestApiError } from "@/lib/api/ai-rest-error";
import type { ConsistencyCheckResponse } from "@/lib/api/consistency";
import { consistencyApi } from "@/lib/api/consistency";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { ConsistencyError } from "./ConsistencyError";
import { ConsistencyLoading } from "./ConsistencyLoading";
import { ConsistencyResults } from "./ConsistencyResults";

type ViewState = "idle" | "loading" | "results" | "error";

interface ConsistencyCheckPanelProps {
  novelId: string;
  onClose: () => void;
  onEntityClick?: (entityId: string) => void;
}

export function ConsistencyCheckPanel({
  novelId,
  onClose,
  onEntityClick,
}: ConsistencyCheckPanelProps) {
  const t = useTranslations("studio");

  const {
    state: aiState,
    start: runCheckOp,
    cancel: cancelOp,
    retry: retryOp,
    isLoading,
    isError,
    isComplete,
    isConnectionLost,
  } = useAIOperation<ConsistencyCheckResponse>({
    execute: (signal) => consistencyApi.checkConsistency(novelId, undefined, signal),
    errorMapper: mapRestApiError,
    connectionLossTimeout: 15_000,
  });

  const viewState: ViewState = isConnectionLost
    ? "error"
    : isLoading
      ? "loading"
      : isError
        ? "error"
        : isComplete
          ? "results"
          : "idle";

  const handleRunCheck = useCallback(() => {
    runCheckOp();
  }, [runCheckOp]);

  const handleCancel = useCallback(() => {
    cancelOp();
  }, [cancelOp]);

  const handleRetry = useCallback(() => {
    retryOp();
  }, [retryOp]);

  // Auto-trigger on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: mount-only
  useEffect(() => {
    if (viewState === "idle") runCheckOp();
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => cancelOp();
  }, [cancelOp]);

  // Global Escape handler: close panel
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  const result = aiState.result;
  const error = aiState.error;
  const errorMessage = (error?.userMessage ?? t("worldbuilding.error")) || "Check failed";

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
            <ShieldCheck className="w-5 h-5 text-amber-500 flex-shrink-0" />
            <h3 className="font-medium truncate">
              {t("consistency.checkButton") || "Consistency Check"}
            </h3>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {viewState === "results" && (
            <button
              type="button"
              onClick={handleRunCheck}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
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
          <ConnectionLostBanner onRetry={handleRetry} />
        </div>
      )}

      {/* Summary header */}
      {viewState === "results" && result && (
        <div className="flex items-center gap-4 p-4 border-b border-border bg-muted/30">
          <div className="flex-shrink-0 flex flex-col items-center">
            <div className="text-2xl font-bold text-amber-500">{result.issues.length}</div>
            <div className="text-xs text-muted-foreground">
              {t("worldbuilding.consistency") || "Issues"}
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-muted-foreground">
              {t("worldbuilding.entityCount", { count: result.entity_count }) ||
                `${result.entity_count} entities analyzed`}
            </p>
            <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
              {Object.entries(result.summary).map(([key, count]) =>
                count > 0 ? (
                  <span key={key}>
                    {count} {key.replace(/_/g, " ")}
                  </span>
                ) : null,
              )}
            </div>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          {viewState === "loading" && <ConsistencyLoading onCancel={handleCancel} />}
          {viewState === "error" && (
            <ConsistencyError message={errorMessage} onRetry={handleRetry} />
          )}
          {viewState === "results" && result && (
            <ConsistencyResults result={result} onEntityClick={onEntityClick} />
          )}
        </div>
      </div>
    </div>
  );
}
