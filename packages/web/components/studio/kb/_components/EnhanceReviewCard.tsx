"use client";

/**
 * Single enhancement card with before/after comparison.
 *
 * Renders the field header, original vs suggested values,
 * AI reasoning, and accept/reject actions.
 */

import { Check, X } from "lucide-react";

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

      {/* Before/After comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-border">
        {/* Original */}
        <div className="p-4">
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
            {t("kb.original")}
          </div>
          <div className="text-sm text-muted-foreground whitespace-pre-wrap line-through opacity-70">
            {enhancement.original || <span className="italic">{t("kb.empty")}</span>}
          </div>
        </div>

        {/* Suggested */}
        <div className="p-4">
          <div className="text-xs font-medium text-green-600 dark:text-green-400 uppercase tracking-wider mb-2">
            {t("kb.suggested")}
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
