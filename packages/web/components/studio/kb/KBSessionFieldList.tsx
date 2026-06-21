"use client";

/**
 * KB Session Field List — Displays all fields in a creation session.
 *
 * Groups fields by status (empty / user-filled / ai-suggested),
 * shows progress, and renders individual field editors.
 */

import { MessageSquare, Wand2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { KBCreationSession } from "@/lib/api/kb-sessions";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { groupFieldsByStatus, isFieldFilled } from "./_components/field-grouping";
import { FieldGroupSection } from "./FieldGroupSection";
import { KBSessionFieldRow } from "./KBSessionFieldRow";

interface KBSessionFieldListProps {
  session: KBCreationSession;
  onSuggest: (fieldKey: string) => void;
  onAnswer: (fieldKey: string, value: string) => void;
  onAcceptSuggestion: (fieldKey: string, value: string) => void;
  onRejectSuggestion: (fieldKey: string) => void;
  onStartInterview: () => void;
  onEnhance: () => void;
  suggestingFieldKey?: string | null;
  suggestionError?: AIErrorResponse | null;
  suggestionErrorFieldKey?: string | null;
  onCancelSuggest?: () => void;
}

export function KBSessionFieldList({
  session,
  onSuggest,
  onAnswer,
  onAcceptSuggestion,
  onRejectSuggestion,
  onStartInterview,
  onEnhance,
  suggestingFieldKey = null,
  suggestionError = null,
  suggestionErrorFieldKey = null,
  onCancelSuggest,
}: KBSessionFieldListProps) {
  const t = useTranslations("studio");

  // Calculate progress
  const totalFields = session.fields.length;
  const filledFields = session.fields.filter(isFieldFilled).length;

  // Group fields by status
  const {
    empty: emptyFields,
    ai: aiFields,
    user: userFields,
    merged: mergedFields,
  } = groupFieldsByStatus(session.fields);

  return (
    <div className="space-y-4">
      {/* Progress and action buttons */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {t("kb.sessionProgress", { filled: filledFields, total: totalFields })}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onStartInterview}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            {t("kb.startInterview")}
          </button>
          <button
            type="button"
            onClick={onEnhance}
            disabled={filledFields === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors disabled:opacity-50"
          >
            <Wand2 className="w-3.5 h-3.5" />
            {t("kb.enhanceAll")}
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-primary transition-all duration-300"
          style={{ width: totalFields > 0 ? `${(filledFields / totalFields) * 100}%` : "0%" }}
        />
      </div>

      {/* Fields */}
      <div className="space-y-3">
        {/* Empty fields (needs input) */}
        {emptyFields.length > 0 && (
          <FieldGroupSection
            title={t("kb.toFill")}
            count={emptyFields.length}
            titleClassName="text-muted-foreground"
          >
            {emptyFields.map((field) => (
              <KBSessionFieldRow
                key={field.field_key}
                field={field}
                isEmpty
                suggestingFieldKey={suggestingFieldKey}
                suggestionError={suggestionError}
                suggestionErrorFieldKey={suggestionErrorFieldKey}
                onCancelSuggest={onCancelSuggest}
                onSuggest={onSuggest}
                onAnswer={onAnswer}
                onAcceptSuggestion={onAcceptSuggestion}
                onRejectSuggestion={onRejectSuggestion}
              />
            ))}
          </FieldGroupSection>
        )}

        {/* AI suggestions pending review */}
        {aiFields.length > 0 && (
          <FieldGroupSection
            title={t("kb.aiSuggestions")}
            count={aiFields.length}
            titleClassName="text-green-600 dark:text-green-400"
          >
            {aiFields.map((field) => (
              <KBSessionFieldRow
                key={field.field_key}
                field={field}
                suggestingFieldKey={suggestingFieldKey}
                suggestionError={suggestionError}
                suggestionErrorFieldKey={suggestionErrorFieldKey}
                onCancelSuggest={onCancelSuggest}
                onSuggest={onSuggest}
                onAnswer={onAnswer}
                onAcceptSuggestion={onAcceptSuggestion}
                onRejectSuggestion={onRejectSuggestion}
              />
            ))}
          </FieldGroupSection>
        )}

        {/* User-filled fields */}
        {userFields.length > 0 && (
          <FieldGroupSection
            title={t("kb.completed")}
            count={userFields.length}
            titleClassName="text-blue-600 dark:text-blue-400"
          >
            {userFields.map((field) => (
              <KBSessionFieldRow
                key={field.field_key}
                field={field}
                suggestingFieldKey={suggestingFieldKey}
                suggestionError={suggestionError}
                suggestionErrorFieldKey={suggestionErrorFieldKey}
                onCancelSuggest={onCancelSuggest}
                onSuggest={onSuggest}
                onAnswer={onAnswer}
                onAcceptSuggestion={onAcceptSuggestion}
                onRejectSuggestion={onRejectSuggestion}
              />
            ))}
          </FieldGroupSection>
        )}

        {/* Merged / world-derived fields */}
        {mergedFields.length > 0 && (
          <FieldGroupSection
            title={t("kb.fromStory")}
            count={mergedFields.length}
            titleClassName="text-purple-600 dark:text-purple-400"
          >
            {mergedFields.map((field) => (
              <KBSessionFieldRow
                key={field.field_key}
                field={field}
                suggestingFieldKey={suggestingFieldKey}
                suggestionError={suggestionError}
                suggestionErrorFieldKey={suggestionErrorFieldKey}
                onCancelSuggest={onCancelSuggest}
                onSuggest={onSuggest}
                onAnswer={onAnswer}
                onAcceptSuggestion={onAcceptSuggestion}
                onRejectSuggestion={onRejectSuggestion}
              />
            ))}
          </FieldGroupSection>
        )}
      </div>
    </div>
  );
}
