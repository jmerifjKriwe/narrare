"use client";

/**
 * Footer actions for the KB improve panel.
 *
 * Shows back, reject-all, and apply-selected buttons.
 * Renders a compact back-only footer when no suggestions exist.
 */

import { ArrowLeft, Check, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";

interface ImproveFooterActionsProps {
  hasSuggestions: boolean;
  selectedCount: number;
  isApplying: boolean;
  onBack: () => void;
  onRejectAll: () => void;
  onApplySelected: () => void;
}

export function ImproveFooterActions({
  hasSuggestions,
  selectedCount,
  isApplying,
  onBack,
  onRejectAll,
  onApplySelected,
}: ImproveFooterActionsProps) {
  const t = useTranslations("studio");

  return (
    <div className="flex items-center justify-between p-4 border-t border-border bg-card">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-2 px-4 py-2 border border-border rounded-md hover:bg-muted transition-colors text-sm"
      >
        <ArrowLeft className="w-4 h-4" />
        {t("kb.improve.back") || "Back to Entry"}
      </button>
      {hasSuggestions && (
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
            onClick={onApplySelected}
            disabled={selectedCount === 0 || isApplying}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50 text-sm"
          >
            {isApplying ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Check className="w-4 h-4" />
            )}
            {t("kb.applySelected", { count: selectedCount }) || `Apply Selected (${selectedCount})`}
          </button>
        </div>
      )}
    </div>
  );
}
