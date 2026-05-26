"use client";

/**
 * BetaReaderPanelContent — tab content renderer for BetaReaderPanel.
 *
 * Extracted from BetaReaderPanel to keep it under 300 lines (RULE-04).
 * Renders the loading, error, and tab content based on view state.
 */

import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Loader2,
  MessageCircle,
  RefreshCw,
  Star,
} from "lucide-react";

import type { BetaReaderResponse, FeedbackSeverity } from "@/lib/api/analysis";
import { FeedbackCard, feedbackCardItem, questionCardItem, strengthCardItem } from "./FeedbackCard";
import { createScoreDimensions, ScoreRadar } from "./ScoreRadar";

// --- Types ---

export type BetaTab = "strengths" | "issues" | "questions" | "overall";
export type ViewState = "idle" | "loading" | "results" | "error";

export interface BetaReaderPanelContentProps {
  viewState: ViewState;
  activeTab: BetaTab;
  result: BetaReaderResponse | null;
  error: Error | null;
  isPending: boolean;
  onRetry: () => void;
  t: (key: string, params?: Record<string, unknown>) => string;
}

// --- Severity sort ---

const SEVERITY_ORDER: Record<FeedbackSeverity, number> = {
  critical: 0,
  moderate: 1,
  minor: 2,
};

// --- Empty state ---

function EmptyState({ icon: Icon, message }: { icon: typeof CheckCircle2; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <Icon className="w-8 h-8 text-muted-foreground mb-2" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

// --- Tab config (shared with parent for header) ---

export const TAB_CONFIG: { key: BetaTab; icon: typeof Star }[] = [
  { key: "strengths", icon: Star },
  { key: "issues", icon: AlertTriangle },
  { key: "questions", icon: MessageCircle },
  { key: "overall", icon: BookOpen },
];

// --- Component ---

export function BetaReaderPanelContent({
  viewState,
  activeTab,
  result,
  error,
  onRetry,
  t,
}: BetaReaderPanelContentProps) {
  // --- Loading ---
  if (viewState === "loading") {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="relative mb-6">
          <div className="w-16 h-16 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
          </div>
        </div>
        <p className="text-lg font-medium mb-2">{t("loading")}</p>
        <p className="text-sm text-muted-foreground">{t("loadingSubtext")}</p>
        <div className="w-64 h-1.5 bg-muted rounded-full overflow-hidden mt-6">
          <div className="h-full bg-purple-500 animate-pulse" style={{ width: "60%" }} />
        </div>
      </div>
    );
  }

  // --- Error ---
  if (viewState === "error") {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
          <AlertTriangle className="w-6 h-6 text-red-500" />
        </div>
        <p className="text-lg font-medium mb-1">{t("error")}</p>
        <p className="text-sm text-muted-foreground mb-4">{error?.message}</p>
        <button
          type="button"
          onClick={onRetry}
          className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          {t("retry")}
        </button>
      </div>
    );
  }

  // --- Results tabs ---
  if (viewState !== "results" || !result) return null;

  const sortedFeedback = [...result.feedback].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99),
  );

  switch (activeTab) {
    case "strengths":
      return result.strengths.length > 0 ? (
        <div className="space-y-3">
          {result.strengths.map((s) => (
            <FeedbackCard key={`s-${s.category}-${s.title}`} item={strengthCardItem(s)} />
          ))}
        </div>
      ) : (
        <EmptyState icon={CheckCircle2} message={t("empty.issues")} />
      );

    case "issues":
      return sortedFeedback.length > 0 ? (
        <div className="space-y-3">
          {sortedFeedback.map((f) => (
            <FeedbackCard
              key={`f-${f.category}-${f.severity}-${f.title}`}
              item={feedbackCardItem(f)}
            />
          ))}
        </div>
      ) : (
        <EmptyState icon={CheckCircle2} message={t("empty.issues")} />
      );

    case "questions":
      return result.questions.length > 0 ? (
        <div className="space-y-3">
          {result.questions.map((q) => (
            <FeedbackCard
              key={`q-${q.category}-${q.question.slice(0, 40)}`}
              item={questionCardItem(q)}
            />
          ))}
        </div>
      ) : (
        <EmptyState icon={MessageCircle} message={t("empty.questions")} />
      );

    case "overall":
      return (
        <div className="space-y-6">
          <ScoreRadar scores={createScoreDimensions(result.overall, t)} />
          <div>
            <h4 className="text-sm font-medium mb-2">{t("overall.summary")}</h4>
            <p className="text-sm text-muted-foreground">{result.overall.summary}</p>
          </div>
          <div className="space-y-3">
            {createScoreDimensions(result.overall, t).map((dim) => (
              <div key={dim.key}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-muted-foreground">{dim.label}</span>
                  <span className="text-xs font-medium">{dim.value}/10</span>
                </div>
                <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full transition-all duration-500"
                    style={{ width: `${dim.value * 10}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      );
  }
}
