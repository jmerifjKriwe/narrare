"use client";

/**
 * Single enhancement card with before/after comparison.
 *
 * Renders the field header, original vs suggested values,
 * AI reasoning, and accept/reject actions.
 */

import { Check, X } from "lucide-react";

import { AIDiffView } from "@/components/shared/ai-diff/AIDiffView";
import { kbEnhanceFieldAdapter } from "@/lib/ai-diff/adapters/kb-enhance";
import type { AIDiffState } from "@/lib/ai-diff/contracts";
import type { KBEnhancementResult } from "@/lib/api/kb-sessions";

type TranslationValues = Record<string, string | number | Date>;

interface EnhanceReviewCardProps {
  enhancement: KBEnhancementResult;
  isSelected: boolean;
  onToggle: (fieldKey: string) => void;
  onAccept: (fieldKey: string) => void;
  onReject: (fieldKey: string) => void;
  fieldLabel: string;
  t: (key: string, values?: TranslationValues) => string;
}

export function EnhanceReviewCard({
  enhancement,
  isSelected,
  onToggle,
  onAccept,
  onReject,
  fieldLabel,
  t,
}: EnhanceReviewCardProps) {
  return (
    <div
      className={`border rounded-lg overflow-hidden transition-colors ${
        isSelected ? "border-primary/50 bg-primary/5" : "border-border bg-card"
      }`}
    >
      {/* Field header */}
      <button
        type="button"
        className="w-full flex items-center justify-between p-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
        onClick={() => onToggle(enhancement.field_key)}
      >
        <div className="flex items-center gap-3">
          <div
            className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
              isSelected ? "bg-primary border-primary" : "border-muted-foreground/40"
            }`}
          >
            {isSelected && <Check className="w-3.5 h-3.5 text-primary-foreground" />}
          </div>
          <span className="text-sm font-medium">{fieldLabel}</span>
        </div>
        <div className="flex items-center gap-2">
          {isSelected ? (
            <span className="text-xs text-green-600 dark:text-green-400">{t("kb.willApply")}</span>
          ) : (
            <span className="text-xs text-muted-foreground">{t("kb.skipped")}</span>
          )}
        </div>
      </button>

      {/* Before/After comparison via shared field-mode AIDiffView (CR-AUFG-07-18).
          The field label is already shown in the header button above, so it is
          passed as null here to avoid a duplicate label inside AIDiffView. */}
      <div className="px-4 py-3">
        <AIDiffView
          viewModel={kbEnhanceFieldAdapter(enhancement, null)}
          state={isSelected ? ("accepted" satisfies AIDiffState) : "suggested"}
        />
      </div>

      {/* Reasoning */}
      {enhancement.reasoning && (
        <div className="px-4 pb-4">
          <div className="mt-3 pt-3 border-t border-border/50">
            <div className="text-xs text-muted-foreground mb-1">{t("kb.aiReasoning")}</div>
            <div className="text-xs text-muted-foreground italic">{enhancement.reasoning}</div>
          </div>
        </div>
      )}

      {/* Quick accept/reject buttons */}
      <div className="flex justify-end gap-2 p-3 border-t border-border/50 bg-muted/20">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onReject(enhancement.field_key);
          }}
          className="flex items-center gap-1 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors"
        >
          <X className="w-3 h-3" />
          {t("aiActions.reject")}
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onAccept(enhancement.field_key);
          }}
          className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
        >
          <Check className="w-3 h-3" />
          {t("aiActions.accept")}
        </button>
      </div>
    </div>
  );
}
