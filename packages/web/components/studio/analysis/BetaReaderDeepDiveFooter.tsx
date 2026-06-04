"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import type { BetaReaderResponse, FeedbackCategory } from "@/lib/api/analysis";
import type { BetaTab } from "./BetaReaderPanelContent";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BetaReaderDeepDiveFooterProps {
  readonly activeTab: BetaTab;
  readonly result: BetaReaderResponse | null;
  readonly isPending: boolean;
  readonly deepDiveCategory: FeedbackCategory | null;
  readonly onDeepDive: (category: FeedbackCategory) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function topCategory(activeTab: BetaTab, result: BetaReaderResponse): FeedbackCategory | undefined {
  const items =
    activeTab === "strengths"
      ? result.strengths
      : activeTab === "issues"
        ? result.feedback
        : result.questions;
  const categories = items.map((item) => item.category);
  return categories.sort(
    (a, b) => categories.filter((c) => c === b).length - categories.filter((c) => c === a).length,
  )[0];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Deep dive action footer for category beta reader tabs. */
export function BetaReaderDeepDiveFooter({
  activeTab,
  result,
  isPending,
  deepDiveCategory,
  onDeepDive,
}: BetaReaderDeepDiveFooterProps) {
  const t = useTranslations("analysis");

  return (
    <div className="p-4 border-t border-border bg-card">
      <button
        type="button"
        disabled={isPending}
        className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors disabled:opacity-50"
        onClick={() => {
          if (!result) return;
          const category = topCategory(activeTab, result);
          if (category) onDeepDive(category);
        }}
      >
        {isPending ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            {deepDiveCategory
              ? t("deepDiveLoading", { category: t(`categories.${deepDiveCategory}`) })
              : t("deepDive")}
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            {t("deepDive")}
          </>
        )}
      </button>
    </div>
  );
}
