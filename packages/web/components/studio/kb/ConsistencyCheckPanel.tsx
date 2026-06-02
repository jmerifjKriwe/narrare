"use client";

/**
 * ConsistencyCheckPanel — KB consistency check results.
 *
 * Auto-triggers check on mount. Shows issues grouped by category.
 * Sub-components: ConsistencyLoading, ConsistencyError, ConsistencyResults.
 *
 * §16 compliance: AbortController cancel, useConnectionLost,
 * studio.aiActions.* labels, actionable error messages.
 */

import { ArrowLeft, RefreshCw, ShieldCheck, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { ConnectionLostBanner } from "@/components/ui/connection-lost-banner";
import type { ConsistencyCheckResponse } from "@/lib/api/consistency";
import { consistencyApi } from "@/lib/api/consistency";
import { useConnectionLost } from "@/lib/hooks/use-connection-lost";
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
  const [state, setState] = useState<ViewState>("idle");
  const [result, setResult] = useState<ConsistencyCheckResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const {
    isConnectionLost,
    markConnectionLost,
    retry: retryConnection,
  } = useConnectionLost({
    onRetry: () => void runCheck(false),
  });

  const runCheck = useCallback(
    async (refresh = false) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      setState("loading");
      setError(null);
      try {
        const data = await consistencyApi.checkConsistency(
          novelId,
          { refresh },
          abortRef.current.signal,
        );
        setResult(data);
        setState("results");
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        markConnectionLost();
        setError(err instanceof Error ? err : new Error(String(err)));
        setState("error");
      }
    },
    [novelId, markConnectionLost],
  );

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState("idle");
  }, []);

  // biome-ignore lint/correctness/useExhaustiveDependencies: mount-only
  useEffect(() => {
    if (state === "idle") void runCheck(false);
  }, []);
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

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
          {state === "results" && (
            <button
              type="button"
              onClick={() => void runCheck(true)}
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
          <ConnectionLostBanner onRetry={retryConnection} />
        </div>
      )}

      {/* Summary header */}
      {state === "results" && result && (
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
          {state === "loading" && <ConsistencyLoading onCancel={handleCancel} />}
          {state === "error" && error && (
            <ConsistencyError message={error.message} onRetry={() => void runCheck(false)} />
          )}
          {state === "results" && result && (
            <ConsistencyResults result={result} onEntityClick={onEntityClick} />
          )}
        </div>
      </div>
    </div>
  );
}
