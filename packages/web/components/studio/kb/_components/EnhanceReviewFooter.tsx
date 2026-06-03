"use client";

/**
 * Footer actions for enhancement review.
 *
 * Back, reject all, and apply selected buttons.
 */

import { ArrowLeft, Check } from "lucide-react";

type TranslationValues = Record<string, string | number | Date>;

interface EnhanceReviewFooterProps {
  selectedCount: number;
  onBack: () => void;
  onRejectAll: () => void;
  onApply: () => void;
  t: (key: string, values?: TranslationValues) => string;
}

export function EnhanceReviewFooter({
  selectedCount,
  onBack,
  onRejectAll,
  onApply,
  t,
}: EnhanceReviewFooterProps) {
  return (
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
          onClick={onRejectAll}
          className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
        >
          {t("kb.rejectAll") || "Reject All"}
        </button>
        <button
          type="button"
          onClick={onApply}
          disabled={selectedCount === 0}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50 text-sm"
        >
          <Check className="w-4 h-4" />
          {t("kb.applySelected", { count: selectedCount }) || `Apply Selected (${selectedCount})`}
        </button>
      </div>
    </div>
  );
}
