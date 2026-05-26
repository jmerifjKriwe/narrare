"use client";

/**
 * ConsistencyCheckPanel — KB consistency check results.
 *
 * Shows consistency issues grouped by category with severity badges.
 * Reuses ConsistencyCard from WorldbuildingAnalysisCards (RULE-04).
 * Auto-triggers check on mount.
 */

import { AlertTriangle, ArrowLeft, Check, Loader2, RefreshCw, ShieldCheck, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { ConsistencyCheckResponse } from "@/lib/api/consistency";
import { consistencyApi } from "@/lib/api/consistency";
import type { ConsistencyIssue } from "@/lib/api/worldbuilding";
import { ConsistencyCard, groupByCategory } from "./WorldbuildingAnalysisCards";

// --- Types ---

type ViewState = "idle" | "loading" | "results" | "error";

interface ConsistencyCheckPanelProps {
  novelId: string;
  onClose: () => void;
}

// --- Severity sort order ---

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  major: 1,
  minor: 2,
  info: 3,
};

export function ConsistencyCheckPanel({ novelId, onClose }: ConsistencyCheckPanelProps) {
  const t = useTranslations("studio");

  const [state, setState] = useState<ViewState>("idle");
  const [result, setResult] = useState<ConsistencyCheckResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);

  // --- Run check ---

  const runCheck = useCallback(
    async (refresh = false) => {
      setState("loading");
      setError(null);

      try {
        const data = await consistencyApi.checkConsistency(novelId, { refresh });
        setResult(data);
        setState("results");
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setState("error");
      }
    },
    [novelId],
  );

  // Auto-trigger on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount
  useEffect(() => {
    if (state !== "idle") return;
    void runCheck(false);
  }, []);

  // --- Derived data ---

  const issues = result?.issues ?? [];
  const grouped = groupByCategory(issues);

  // --- Render ---

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

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          {/* Loading state */}
          {state === "loading" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="relative mb-6">
                <div className="w-16 h-16 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
                </div>
              </div>
              <p className="text-lg font-medium mb-2">
                {t("consistency.checking") || "Checking consistency..."}
              </p>
              <p className="text-sm text-muted-foreground">
                {t("worldbuilding.analyzingDesc") ||
                  "The AI is reviewing your world for consistency issues..."}
              </p>
              <div className="w-64 h-1.5 bg-muted rounded-full overflow-hidden mt-6">
                <div className="h-full bg-amber-500 animate-pulse" style={{ width: "60%" }} />
              </div>
            </div>
          )}

          {/* Error state */}
          {state === "error" && error && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
                <AlertTriangle className="w-6 h-6 text-red-500" />
              </div>
              <p className="text-lg font-medium mb-1">
                {t("worldbuilding.error") || "Check failed"}
              </p>
              <p className="text-sm text-muted-foreground mb-4">{error.message}</p>
              <button
                type="button"
                onClick={() => void runCheck(false)}
                className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                {t("worldbuilding.retry") || "Retry"}
              </button>
            </div>
          )}

          {/* No issues state */}
          {state === "results" && issues.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-4">
                <Check className="w-6 h-6 text-green-500" />
              </div>
              <p className="text-lg font-medium mb-1">
                {t("consistency.noIssues") || "No issues found!"}
              </p>
              <p className="text-sm text-muted-foreground">
                {t("worldbuilding.noIssuesDesc") ||
                  "Your worldbuilding looks comprehensive and consistent."}
              </p>
            </div>
          )}

          {/* Issues grouped by category */}
          {state === "results" && issues.length > 0 && (
            <div className="space-y-6">
              {Object.entries(grouped).map(([category, categoryIssues]) => (
                <div key={category}>
                  <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">
                    {category.replace(/_/g, " ")}
                    <span className="ml-2 text-xs">({categoryIssues.length})</span>
                  </h4>
                  <div className="space-y-3">
                    {categoryIssues
                      .sort(
                        (a: ConsistencyIssue, b: ConsistencyIssue) =>
                          (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99),
                      )
                      .map((issue: ConsistencyIssue) => (
                        <ConsistencyCard key={issue.finding_index} issue={issue} t={t} />
                      ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
