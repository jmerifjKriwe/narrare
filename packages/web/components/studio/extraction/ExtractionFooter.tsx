"use client";

/**
 * ExtractionFooter — Action buttons for the extraction panel.
 *
 * Cancel + Apply with selected count. Disabled when 0 selected or applying.
 */

import { Check, Loader2, X } from "lucide-react";
import { useTranslations } from "next-intl";

interface ExtractionFooterProps {
  selectedCount: number;
  totalCount: number;
  isApplying: boolean;
  onCancel: () => void;
  onApply: () => void;
}

export function ExtractionFooter({
  selectedCount,
  totalCount,
  isApplying,
  onCancel,
  onApply,
}: ExtractionFooterProps) {
  const t = useTranslations("studio");

  return (
    <div className="flex items-center justify-between p-4 border-t border-border bg-card">
      <button
        type="button"
        onClick={onCancel}
        className="flex items-center gap-2 px-4 py-2 border border-border rounded-md hover:bg-muted transition-colors text-sm"
      >
        <X className="w-4 h-4" />
        {t("kb.extractionCancel")}
      </button>
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">
          {t("kb.extractionSelectedSummary", { count: selectedCount, total: totalCount })}
        </span>
        <button
          type="button"
          onClick={onApply}
          disabled={selectedCount === 0 || isApplying}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50 text-sm"
        >
          {isApplying ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              {t("kb.extractionApplying")}
            </>
          ) : (
            <>
              <Check className="w-4 h-4" />
              {t("kb.extractionApply", { count: selectedCount })}
            </>
          )}
        </button>
      </div>
    </div>
  );
}
