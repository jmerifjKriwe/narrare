"use client";

/**
 * KB Improve Panel — AI-powered entry improvement review.
 *
 * Analyzes a KB entry and presents suggestions (add_field, connect,
 * expand, reorganize) with per-suggestion selection and bulk apply.
 *
 * Auto-triggers analysis on mount. Follows the same patterns as
 * KBEnhanceReview.tsx for consistency.
 */

import { ArrowLeft, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import type { ImproveSuggestion, KBImproveAnalysisResponse } from "@/lib/api/kb-improve";
import { useKBImproveAnalysis, useKBImproveApply } from "@/lib/hooks/useKBImprove";

import { ImproveErrorState } from "./_components/ImproveErrorState";
import { ImproveFooterActions } from "./_components/ImproveFooterActions";
import { ImproveLoadingState } from "./_components/ImproveLoadingState";
import { ImproveReviewSection } from "./_components/ImproveReviewSection";

type ImproveViewState = "idle" | "loading" | "review" | "error";

interface KBImprovePanelProps {
  novelId: string;
  entryId: string;
  onClose: () => void;
  onApplied: () => void;
}

export function KBImprovePanel({ novelId, entryId, onClose, onApplied }: KBImprovePanelProps) {
  const t = useTranslations("studio");
  const [state, setState] = useState<ImproveViewState>("idle");
  const [suggestions, setSuggestions] = useState<ImproveSuggestion[]>([]);
  const [assessment, setAssessment] = useState("");
  const [completenessScore, setCompletenessScore] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [error, setError] = useState<Error | null>(null);

  const analyzeMutation = useKBImproveAnalysis(novelId, entryId);
  const applyMutation = useKBImproveApply(novelId, entryId);

  async function runAnalysis() {
    setState("loading");
    setError(null);

    try {
      const result: KBImproveAnalysisResponse = await analyzeMutation.mutateAsync();
      setSuggestions(result.suggestions);
      setAssessment(result.overall_assessment);
      setCompletenessScore(result.completeness_score);
      // Auto-select high-confidence suggestions (>= 0.7)
      setSelectedIds(
        new Set(result.suggestions.filter((s) => s.confidence >= 0.7).map((s) => s.suggestion_id)),
      );
      setState("review");
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setState("error");
    }
  }

  // Auto-trigger analysis on mount — intentional mount-trigger pattern
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount
  useEffect(() => {
    if (state !== "idle") return;
    void runAnalysis();
  }, []);

  function toggleSuggestion(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function selectAll() {
    setSelectedIds(new Set(suggestions.map((s) => s.suggestion_id)));
  }

  function selectNone() {
    setSelectedIds(new Set());
  }

  function acceptSuggestion(id: number) {
    setSelectedIds((prev) => new Set(prev).add(id));
  }

  function rejectSuggestion(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  async function applySelected() {
    try {
      const result = await applyMutation.mutateAsync(Array.from(selectedIds));
      if (result.success) {
        onApplied();
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setState("error");
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-500" />
            <h3 className="font-medium">{t("kb.improve.title") || "AI Suggestions"}</h3>
          </div>
        </div>
        {state === "review" && (
          <div className="text-sm text-muted-foreground">
            {t("kb.improve.selectedCount", {
              count: selectedIds.size,
              total: suggestions.length,
            }) || `${selectedIds.size} of ${suggestions.length} selected`}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {state === "loading" && <ImproveLoadingState />}

          {state === "error" && error && <ImproveErrorState error={error} onRetry={runAnalysis} />}

          {state === "review" && (
            <ImproveReviewSection
              completenessScore={completenessScore}
              assessment={assessment}
              suggestions={suggestions}
              selectedIds={selectedIds}
              onSelectAll={selectAll}
              onSelectNone={selectNone}
              onToggleSuggestion={toggleSuggestion}
              onAcceptSuggestion={acceptSuggestion}
              onRejectSuggestion={rejectSuggestion}
            />
          )}
        </div>
      </div>

      {/* Footer */}
      {state === "review" && (
        <ImproveFooterActions
          hasSuggestions={suggestions.length > 0}
          selectedCount={selectedIds.size}
          isApplying={applyMutation.isPending}
          onBack={onClose}
          onRejectAll={selectNone}
          onApplySelected={applySelected}
        />
      )}
    </div>
  );
}
