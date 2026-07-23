"use client";

import { Brain, RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import { LearningStatus } from "@/components/studio/learning/LearningStatus";
import { AnalysisErrorBanner } from "@/components/studio/settings/_components/AnalysisErrorBanner";
import { AdaptiveDashboard } from "@/components/studio/settings/AdaptiveDashboard";
import { PreferenceProfile } from "@/components/studio/settings/PreferenceProfile";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import { usePreferences, useResetPreferences, useTriggerAnalysis } from "@/lib/hooks/useMemory";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LearningTabProps {
  readonly novelId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LearningTab({ novelId }: LearningTabProps) {
  const t = useTranslations("studio");
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const { data: profile, isLoading, error } = usePreferences(novelId);
  const resetMutation = useResetPreferences(novelId);
  const analysisMutation = useTriggerAnalysis(novelId);

  const handleReset = useCallback(() => {
    resetMutation.mutate(undefined, {
      onSuccess: () => setShowResetConfirm(false),
    });
  }, [resetMutation]);

  const handleAnalyze = useCallback(() => {
    analysisMutation.mutate();
  }, [analysisMutation]);

  // --- Loading state ---
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-pulse text-sm text-muted-foreground">{t("learning.loading")}</div>
      </div>
    );
  }

  // --- Error state ---
  // Route the profile-fetch error through the canonical mapper (ADR-043 §16.5)
  // so the raw underlying error text is never leaked. mapSSEError returns null
  // for aborts.
  if (error) {
    const errorMsg = mapSSEError(error)?.userMessage ?? t("learning.loadFailed");
    return (
      <div className="bg-destructive/10 text-destructive rounded-lg p-4 text-sm" role="alert">
        {errorMsg}
      </div>
    );
  }

  // --- No profile yet ---
  const eventCount = profile?.event_count ?? 0;

  // Preference analysis is an AI operation (LLM). Route its error through the
  // canonical mapper (ADR-043 §16.5) so the raw underlying error never leaks,
  // and surface retry + connection-lost indication for §16.4 UX parity with
  // GenerationPanel. mapSSEError returns null for aborts (no banner shown).
  const analysisError = analysisMutation.error ? mapSSEError(analysisMutation.error) : null;
  const isAnalysisConnectionLost = analysisError?.kind === "network";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-xl font-medium mb-1">{t("learning.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("learning.description")}</p>
      </div>

      {/* Adaptive Context dashboard (LEARN-002, ADR-069 §25).
          Mounted as the primary control above progress + preference profile:
          toggle → weights → sources hierarchy. All state flows through the
          canonical adaptive-context query key (Decision 15). */}
      <AdaptiveDashboard novelId={novelId} />

      {/* Progress section */}
      <div className="bg-card border border-border rounded-lg p-6">
        <LearningStatus eventCount={eventCount} />
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleAnalyze}
          disabled={analysisMutation.isPending || eventCount < 5}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
        >
          <Brain className="w-4 h-4" />
          <span>
            {analysisMutation.isPending ? t("learning.analyzing") : t("learning.analyze")}
          </span>
        </button>

        {/* Insufficient events hint */}
        {eventCount < 5 && (
          <span className="text-xs text-muted-foreground">
            {t("learning.minEventsHint", { current: eventCount, min: 5 })}
          </span>
        )}
      </div>

      {/* Analysis error — mapped message + retry, with connection-lost styling
           when the failure is a network error (§16.4 parity with GenerationPanel) */}
      <AnalysisErrorBanner
        analysisError={analysisError}
        isConnectionLost={isAnalysisConnectionLost}
        isPending={analysisMutation.isPending}
        onRetry={handleAnalyze}
      />

      {/* Preference Profile */}
      {profile && (
        <div className="bg-card border border-border rounded-lg p-6">
          <PreferenceProfile profile={profile} />
        </div>
      )}

      {/* No data state */}
      {!profile && (
        <div className="bg-card border border-border rounded-lg p-6 text-center">
          <p className="text-sm text-muted-foreground">{t("learning.noData")}</p>
        </div>
      )}

      {/* Reset section */}
      <div className="border-t border-border pt-6">
        {!showResetConfirm ? (
          <button
            type="button"
            onClick={() => setShowResetConfirm(true)}
            className="flex items-center gap-2 px-3 py-2 text-sm text-destructive hover:bg-destructive/10 rounded-lg transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            <span>{t("learning.reset")}</span>
          </button>
        ) : (
          <div className="flex items-center gap-3 p-3 rounded-lg bg-destructive/10">
            <span className="text-sm text-destructive">{t("learning.resetConfirm")}</span>
            <button
              type="button"
              onClick={handleReset}
              disabled={resetMutation.isPending}
              className="px-3 py-1 text-xs font-medium rounded-md bg-destructive text-white hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {resetMutation.isPending ? t("learning.resetting") : t("learning.confirmReset")}
            </button>
            <button
              type="button"
              onClick={() => setShowResetConfirm(false)}
              className="px-3 py-1 text-xs font-medium rounded-md border border-border text-foreground hover:bg-accent transition-colors"
            >
              {t("learning.cancelReset")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
