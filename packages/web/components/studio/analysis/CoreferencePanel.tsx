"use client";

/**
 * CoreferencePanel — collapsible side panel for Coreference Analysis (ANAL-005).
 *
 * Shows the referential-clarity score (gauge), a pronoun-resolution table
 * (pronoun → referent with confidence + ambiguity flag), character mentions
 * with POV indicators, and a free-text summary.
 *
 * Lifecycle runs through {@link useCoreference} → `useAIOperation` (ADR-043):
 * no manual AbortController. Follows the POVPanel layout (400px wide,
 * border-left). The results view is extracted into
 * {@link ./_components/CoreferenceResults} per RULE-04.
 */

import { ArrowLeft, Info, Loader2, RefreshCw, Users, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef } from "react";
import { AnalysisPanelWrapper } from "@/components/ui/analysis-panel-wrapper";
import { useCoreference } from "@/lib/hooks/useCoreference";
import { CoreferenceResults } from "./_components/CoreferenceResults";

// --- Types ---

interface CoreferencePanelProps {
  novelId: string;
  chapterIds: string[];
  onClose: () => void;
}

type ViewState = "idle" | "loading" | "results" | "error";

// --- Component ---

export function CoreferencePanel({ novelId, chapterIds, onClose }: CoreferencePanelProps) {
  // novelId is part of the panel contract (mirrors POVPanel/ReadabilityPanel);
  // the coreference endpoint is scoped to a single chapter via its path param.
  void novelId;

  const t = useTranslations("analysis");
  const chapterId = chapterIds[0] ?? null;

  const { result, error, run, isLoading, isStreaming, isComplete, isError } =
    useCoreference(chapterId);
  const startedRef = useRef(false);

  // Auto-trigger analysis once a chapter is available.
  useEffect(() => {
    if (startedRef.current || !chapterId) return;
    startedRef.current = true;
    run(chapterId);
  }, [chapterId, run]);

  const inFlight = isLoading || isStreaming;

  const viewState: ViewState = !chapterId
    ? "idle"
    : isError
      ? "error"
      : isComplete && result
        ? "results"
        : "loading";

  const handleRetry = () => {
    if (chapterId) run(chapterId);
  };

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
            <Users className="w-5 h-5 text-sky-500 flex-shrink-0" />
            <h3 className="font-medium truncate">{t("coreference.title")}</h3>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {viewState === "results" && (
            <button
              type="button"
              onClick={handleRetry}
              disabled={inFlight}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors disabled:opacity-50"
              aria-label={t("refresh")}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${inFlight ? "animate-spin" : ""}`} />
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
          {t("coreference.description")}
        </p>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          <AnalysisPanelWrapper phase={viewState}>
            {/* Loading state */}
            {viewState === "loading" && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="relative mb-6">
                  <div className="w-16 h-16 rounded-full bg-sky-100 dark:bg-sky-900/30 flex items-center justify-center">
                    <Loader2 className="w-8 h-8 text-sky-500 animate-spin" />
                  </div>
                </div>
                <p className="text-lg font-medium mb-2">{t("coreference.analyzing")}</p>
                <p className="text-sm text-muted-foreground">{t("coreference.analyzingSubtext")}</p>
              </div>
            )}

            {/* Error state */}
            {viewState === "error" && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
                  <Info className="w-6 h-6 text-red-500" />
                </div>
                <p className="text-lg font-medium mb-1">{t("coreference.analysisFailed")}</p>
                <p className="text-sm text-muted-foreground mb-4">{error?.userMessage}</p>
                <button
                  type="button"
                  onClick={handleRetry}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
                >
                  <RefreshCw className="w-4 h-4" />
                  {t("retry")}
                </button>
              </div>
            )}

            {/* Results */}
            {viewState === "results" && result && <CoreferenceResults result={result} t={t} />}
          </AnalysisPanelWrapper>
        </div>
      </div>
    </div>
  );
}
