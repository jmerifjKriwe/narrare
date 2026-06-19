"use client";

/**
 * FieldSuggestionReview — inline AI suggestion accept/reject view.
 *
 * Renders a pending AI suggestion with its reasoning and the accept/reject
 * actions. Used by KBSessionFieldRow when a field has an unaccepted AI
 * suggestion (source === "ai" && !final_value).
 *
 * Extracted from KBSessionFieldRow for RULE-04 compliance (one
 * responsibility per file: AI-suggestion review UI).
 */

import { Check, X } from "lucide-react";
import { useTranslations } from "next-intl";
import type { KBCreationField } from "@/lib/api/kb-sessions";

interface FieldSuggestionReviewProps {
  field: KBCreationField;
  onAcceptSuggestion: (fieldKey: string, value: string) => void;
  onRejectSuggestion: (fieldKey: string) => void;
}

export function FieldSuggestionReview({
  field,
  onAcceptSuggestion,
  onRejectSuggestion,
}: FieldSuggestionReviewProps) {
  const t = useTranslations("studio");

  return (
    <div className="space-y-2">
      <div className="p-3 bg-green-50 dark:bg-green-950/20 rounded-md border border-green-200 dark:border-green-900/30">
        <div className="text-sm whitespace-pre-wrap">{field.ai_suggested_value}</div>
      </div>
      {field.ai_reasoning && (
        <div className="text-xs text-muted-foreground italic px-1">{field.ai_reasoning}</div>
      )}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => onRejectSuggestion(field.field_key)}
          className="flex items-center gap-1 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors"
        >
          <X className="w-3 h-3" />
          {t("aiActions.reject")}
        </button>
        <button
          type="button"
          onClick={() => onAcceptSuggestion(field.field_key, field.ai_suggested_value!)}
          className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
        >
          <Check className="w-3 h-3" />
          {t("aiActions.accept")}
        </button>
      </div>
    </div>
  );
}
