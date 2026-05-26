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

import {
  ArrowLeft,
  Check,
  Expand,
  Link2,
  Loader2,
  PlusCircle,
  RotateCcw,
  Shuffle,
  Sparkles,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import type { ImproveSuggestion, KBImproveAnalysisResponse } from "@/lib/api/kb-improve";
import { useKBImproveAnalysis, useKBImproveApply } from "@/lib/hooks/useKBImprove";

type ImproveViewState = "idle" | "loading" | "review" | "error";

interface KBImprovePanelProps {
  novelId: string;
  entryId: string;
  onClose: () => void;
  onApplied: () => void;
}

// --- Type icon map ---

const TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  add_field: PlusCircle,
  connect: Link2,
  expand: Expand,
  reorganize: Shuffle,
};

const TYPE_COLORS: Record<string, string> = {
  add_field: "text-blue-500 bg-blue-100 dark:bg-blue-900/30",
  connect: "text-purple-500 bg-purple-100 dark:bg-purple-900/30",
  expand: "text-green-500 bg-green-100 dark:bg-green-900/30",
  reorganize: "text-amber-500 bg-amber-100 dark:bg-amber-900/30",
};

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

  async function applySelected() {
    try {
      const result = await applyMutation.mutateAsync(Array.from(selectedIds));
      if (result.success) {
        onApplied();
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    }
  }

  function getTypeLabel(type: string): string {
    const key = `kb.improve.type.${type}`;
    const v = t(key);
    return v !== key ? v : type.replace(/_/g, " ");
  }

  const TypeIcon = (type: string) => TYPE_ICONS[type] ?? Sparkles;

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
          {/* Loading state */}
          {state === "loading" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="relative mb-6">
                <div className="w-16 h-16 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
                </div>
              </div>
              <p className="text-lg font-medium mb-2">
                {t("kb.improve.running") || "Analyzing entry..."}
              </p>
              <p className="text-sm text-muted-foreground">
                {t("kb.aiEnhancingDesc") || "The AI is reviewing and enhancing your entry..."}
              </p>
              {/* Progress indicator */}
              <div className="w-64 h-1.5 bg-muted rounded-full overflow-hidden mt-6">
                <div className="h-full bg-purple-500 animate-pulse" style={{ width: "60%" }} />
              </div>
            </div>
          )}

          {/* Error state */}
          {state === "error" && error && (
            <div className="p-4 border border-red-200 dark:border-red-900/50 rounded-lg bg-red-50 dark:bg-red-950/20">
              <div className="flex items-center justify-between">
                <p className="text-sm text-red-600 dark:text-red-400">
                  {error.message || t("kb.improve.analysisError") || "Analysis failed"}
                </p>
                <button
                  type="button"
                  onClick={runAnalysis}
                  className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-700"
                >
                  <RotateCcw className="w-3 h-3" />
                  {t("kb.retry") || "Retry"}
                </button>
              </div>
            </div>
          )}

          {/* Review state */}
          {state === "review" && (
            <div className="space-y-4">
              {/* Completeness score + assessment */}
              <div className="flex items-start gap-4 p-4 bg-muted/30 rounded-lg">
                <div className="flex-shrink-0 flex flex-col items-center">
                  <div className="text-2xl font-bold text-purple-500">
                    {Math.round(completenessScore * 100)}%
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {t("kb.improve.completeness") || "Complete"}
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  {/* Score bar */}
                  <div className="w-full h-2 bg-muted rounded-full overflow-hidden mb-2">
                    <div
                      className="h-full bg-purple-500 rounded-full transition-all duration-500"
                      style={{ width: `${Math.round(completenessScore * 100)}%` }}
                    />
                  </div>
                  <p className="text-sm text-muted-foreground">{assessment}</p>
                </div>
              </div>

              {/* Bulk actions */}
              {suggestions.length > 0 && (
                <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm text-muted-foreground">
                    {t("kb.enhancementsFound", { count: suggestions.length }) ||
                      `${suggestions.length} suggestion(s) found`}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={selectAll}
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      {t("kb.selectAll") || "Select all"}
                    </button>
                    <span className="text-muted-foreground">|</span>
                    <button
                      type="button"
                      onClick={selectNone}
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      {t("kb.selectNone") || "Select none"}
                    </button>
                  </div>
                </div>
              )}

              {/* No suggestions state */}
              {suggestions.length === 0 && (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-4">
                    <Check className="w-6 h-6 text-green-500" />
                  </div>
                  <p className="text-lg font-medium mb-1">
                    {t("kb.improve.noSuggestions") || "No improvement suggestions found."}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {t("kb.improve.entryLooksGood") || "The entry looks comprehensive."}
                  </p>
                </div>
              )}

              {/* Suggestion cards */}
              {suggestions.map((suggestion) => {
                const IconComponent = TypeIcon(suggestion.type);
                const isSelected = selectedIds.has(suggestion.suggestion_id);
                const colorClass = TYPE_COLORS[suggestion.type] ?? "text-gray-500 bg-gray-100";

                return (
                  <div
                    key={suggestion.suggestion_id}
                    className={`border rounded-lg overflow-hidden transition-colors ${
                      isSelected ? "border-primary/50 bg-primary/5" : "border-border bg-card"
                    }`}
                  >
                    {/* Suggestion header */}
                    <button
                      type="button"
                      className="w-full flex items-center justify-between p-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
                      onClick={() => toggleSuggestion(suggestion.suggestion_id)}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                            isSelected ? "bg-primary border-primary" : "border-muted-foreground/40"
                          }`}
                        >
                          {isSelected && <Check className="w-3.5 h-3.5 text-primary-foreground" />}
                        </div>
                        <div
                          className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 ${colorClass}`}
                        >
                          <IconComponent className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                              {getTypeLabel(suggestion.type)}
                            </span>
                            <span className="text-xs text-purple-500 font-medium">
                              {Math.round(suggestion.confidence * 100)}%
                            </span>
                          </div>
                          <p className="text-sm font-medium truncate">{suggestion.description}</p>
                        </div>
                      </div>
                      {isSelected && (
                        <span className="text-xs text-green-600 dark:text-green-400 flex-shrink-0">
                          {t("kb.willApply") || "Will apply"}
                        </span>
                      )}
                    </button>

                    {/* Confidence bar */}
                    <div className="px-4 py-1.5">
                      <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-purple-400/60 rounded-full"
                          style={{ width: `${Math.round(suggestion.confidence * 100)}%` }}
                        />
                      </div>
                    </div>

                    {/* Proposed content or related entity */}
                    {(suggestion.proposed_content || suggestion.related_entity_name) && (
                      <div className="px-4 pb-2">
                        <div className="p-3 bg-muted/20 rounded-md text-sm text-muted-foreground">
                          {suggestion.proposed_content ? (
                            <span className="italic">
                              {"\u201c"}
                              {suggestion.proposed_content}
                              {"\u201d"}
                            </span>
                          ) : null}
                          {suggestion.related_entity_name ? (
                            <span>
                              {suggestion.proposed_content ? <br /> : null}
                              <span className="text-xs font-medium text-purple-500">
                                {suggestion.related_entity_name}
                              </span>
                            </span>
                          ) : null}
                        </div>
                      </div>
                    )}

                    {/* Reasoning */}
                    {suggestion.reasoning && (
                      <div className="px-4 pb-3">
                        <div className="text-xs text-muted-foreground italic">
                          {suggestion.reasoning}
                        </div>
                      </div>
                    )}

                    {/* Quick accept/reject buttons */}
                    <div className="flex justify-end gap-2 p-3 border-t border-border/50 bg-muted/20">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          const next = new Set(selectedIds);
                          next.delete(suggestion.suggestion_id);
                          setSelectedIds(next);
                        }}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors"
                      >
                        <X className="w-3 h-3" />
                        {t("kb.reject") || "Reject"}
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          const next = new Set(selectedIds);
                          next.add(suggestion.suggestion_id);
                          setSelectedIds(next);
                        }}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
                      >
                        <Check className="w-3 h-3" />
                        {t("kb.accept") || "Accept"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Footer actions */}
      {state === "review" && suggestions.length > 0 && (
        <div className="flex items-center justify-between p-4 border-t border-border bg-card">
          <button
            type="button"
            onClick={onClose}
            className="flex items-center gap-2 px-4 py-2 border border-border rounded-md hover:bg-muted transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            {t("kb.improve.back") || "Back to Entry"}
          </button>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={selectNone}
              className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
            >
              {t("kb.rejectAll") || "Reject All"}
            </button>
            <button
              type="button"
              onClick={applySelected}
              disabled={selectedIds.size === 0 || applyMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50 text-sm"
            >
              {applyMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              {t("kb.applySelected", { count: selectedIds.size }) ||
                `Apply Selected (${selectedIds.size})`}
            </button>
          </div>
        </div>
      )}

      {/* Footer for empty review — only back button */}
      {state === "review" && suggestions.length === 0 && (
        <div className="flex items-center justify-between p-4 border-t border-border bg-card">
          <button
            type="button"
            onClick={onClose}
            className="flex items-center gap-2 px-4 py-2 border border-border rounded-md hover:bg-muted transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            {t("kb.improve.back") || "Back to Entry"}
          </button>
        </div>
      )}
    </div>
  );
}
