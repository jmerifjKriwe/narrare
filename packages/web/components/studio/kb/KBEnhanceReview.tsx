"use client";

/**
 * KB Enhance Review — AI enhancement review interface.
 *
 * Shows before/after comparisons for AI-enhanced fields,
 * with accept/reject per field and bulk actions.
 */

import { ArrowLeft, Check, Loader2, RotateCcw, Wand2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import type { KBCreationSession, KBEnhancementResult } from "@/lib/api/kb-sessions";

type EnhanceViewState = "idle" | "loading" | "review" | "error";

interface KBEnhanceReviewProps {
  session: KBCreationSession;
  onRequestEnhance: () => Promise<KBEnhancementResult[]>;
  onAcceptEnhancement: (fieldKey: string, value: string) => void;
  onApplySelected: () => void;
  onBack: () => void;
}

export function KBEnhanceReview({
  session,
  onRequestEnhance,
  onAcceptEnhancement,
  onApplySelected,
  onBack,
}: KBEnhanceReviewProps) {
  const t = useTranslations("studio");
  const [state, setState] = useState<EnhanceViewState>("idle");
  const [enhancements, setEnhancements] = useState<KBEnhancementResult[]>([]);
  const [selectedFieldKeys, setSelectedFieldKeys] = useState<Set<string>>(new Set());
  const [error, setError] = useState<Error | null>(null);

  async function requestEnhancement() {
    setState("loading");
    setError(null);

    try {
      const results = await onRequestEnhance();
      setEnhancements(results);
      // Auto-select all by default
      setSelectedFieldKeys(new Set(results.map((e) => e.field_key)));
      setState("review");
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setState("error");
    }
  }

  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount — intentional mount-trigger pattern
  useEffect(() => {
    if (state !== "idle") return;

    const run = async () => {
      setState("loading");
      try {
        const results = await onRequestEnhance();
        setEnhancements(results);
        setSelectedFieldKeys(new Set(results.map((e) => e.field_key)));
        setState("review");
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setState("error");
      }
    };
    void run();
  }, []);

  function toggleFieldSelection(fieldKey: string) {
    setSelectedFieldKeys((prev) => {
      const next = new Set(prev);
      if (next.has(fieldKey)) {
        next.delete(fieldKey);
      } else {
        next.add(fieldKey);
      }
      return next;
    });
  }

  function selectAll() {
    setSelectedFieldKeys(new Set(enhancements.map((e) => e.field_key)));
  }

  function selectNone() {
    setSelectedFieldKeys(new Set());
  }

  function applySelected() {
    // Apply each selected enhancement
    for (const fieldKey of selectedFieldKeys) {
      const enhancement = enhancements.find((e) => e.field_key === fieldKey);
      if (enhancement) {
        onAcceptEnhancement(fieldKey, enhancement.suggested);
      }
    }
    onApplySelected();
  }

  // Get field label from session
  function getFieldLabel(fieldKey: string): string {
    return session.fields.find((f) => f.field_key === fieldKey)?.label || fieldKey;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2">
            <Wand2 className="w-5 h-5 text-purple-500" />
            <h3 className="font-medium">{t("kb.enhanceReview") || "Enhance Review"}</h3>
          </div>
        </div>
        {state === "review" && (
          <div className="text-sm text-muted-foreground">
            {t("kb.enhanceSelected", {
              count: selectedFieldKeys.size,
              total: enhancements.length,
            }) || `${selectedFieldKeys.size} of ${enhancements.length} selected`}
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
              <p className="text-lg font-medium mb-2">{t("kb.aiEnhancing")}</p>
              <p className="text-sm text-muted-foreground">
                {t("kb.aiEnhancingDesc") || "The AI is reviewing and enhancing your entry..."}
              </p>
              {/* Progress bar */}
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
                  {error.message || "Enhancement failed"}
                </p>
                <button
                  type="button"
                  onClick={requestEnhancement}
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
              {/* Bulk actions */}
              <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className="text-sm text-muted-foreground">
                    {t("kb.enhancementsFound", { count: enhancements.length }) ||
                      `${enhancements.length} enhancement(s) found`}
                  </span>
                </div>
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

              {/* Enhancement cards */}
              {enhancements.map((enhancement) => {
                const isSelected = selectedFieldKeys.has(enhancement.field_key);

                return (
                  <div
                    key={enhancement.field_key}
                    className={`border rounded-lg overflow-hidden transition-colors ${
                      isSelected ? "border-primary/50 bg-primary/5" : "border-border bg-card"
                    }`}
                  >
                    {/* Field header */}
                    <button
                      type="button"
                      className="w-full flex items-center justify-between p-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
                      onClick={() => toggleFieldSelection(enhancement.field_key)}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                            isSelected ? "bg-primary border-primary" : "border-muted-foreground/40"
                          }`}
                        >
                          {isSelected && <Check className="w-3.5 h-3.5 text-primary-foreground" />}
                        </div>
                        <span className="text-sm font-medium">
                          {getFieldLabel(enhancement.field_key)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {isSelected ? (
                          <span className="text-xs text-green-600 dark:text-green-400">
                            {t("kb.willApply") || "Will apply"}
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            {t("kb.skipped") || "Skipped"}
                          </span>
                        )}
                      </div>
                    </button>

                    {/* Before/After comparison */}
                    <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-border">
                      {/* Original */}
                      <div className="p-4">
                        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                          {t("kb.original") || "Original"}
                        </div>
                        <div className="text-sm text-muted-foreground whitespace-pre-wrap line-through opacity-70">
                          {enhancement.original || (
                            <span className="italic">{t("kb.empty") || "(empty)"}</span>
                          )}
                        </div>
                      </div>

                      {/* Suggested */}
                      <div className="p-4">
                        <div className="text-xs font-medium text-green-600 dark:text-green-400 uppercase tracking-wider mb-2">
                          {t("kb.suggested") || "Suggested"}
                        </div>
                        <div className="text-sm whitespace-pre-wrap">{enhancement.suggested}</div>
                      </div>
                    </div>

                    {/* Reasoning */}
                    {enhancement.reasoning && (
                      <div className="px-4 pb-4">
                        <div className="mt-3 pt-3 border-t border-border/50">
                          <div className="text-xs text-muted-foreground mb-1">
                            {t("kb.aiReasoning") || "Why the AI suggests this"}
                          </div>
                          <div className="text-xs text-muted-foreground italic">
                            {enhancement.reasoning}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Quick accept/reject buttons */}
                    <div className="flex justify-end gap-2 p-3 border-t border-border/50 bg-muted/20">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          const next = new Set(selectedFieldKeys);
                          next.delete(enhancement.field_key);
                          setSelectedFieldKeys(next);
                        }}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors"
                      >
                        <X className="w-3 h-3" />
                        {t("kb.reject")}
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          const next = new Set(selectedFieldKeys);
                          next.add(enhancement.field_key);
                          setSelectedFieldKeys(next);
                        }}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
                      >
                        <Check className="w-3 h-3" />
                        {t("kb.accept")}
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
      {state === "review" && (
        <div className="flex items-center justify-between p-4 border-t border-border bg-card">
          <button
            type="button"
            onClick={onBack}
            className="flex items-center gap-2 px-4 py-2 border border-border rounded-md hover:bg-muted transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            {t("kb.backToFieldList") || "Back to Field List"}
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
              disabled={selectedFieldKeys.size === 0}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50 text-sm"
            >
              <Check className="w-4 h-4" />
              {t("kb.applySelected", { count: selectedFieldKeys.size }) ||
                `Apply Selected (${selectedFieldKeys.size})`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
