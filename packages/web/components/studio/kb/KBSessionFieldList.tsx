"use client";

/**
 * KB Session Field List — Displays all fields in a creation session.
 *
 * Groups fields by status (empty / user-filled / ai-suggested),
 * shows progress, and renders individual field editors.
 */

import { Check, Edit3, MessageSquare, Sparkles, Wand2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import type { KBCreationField, KBCreationSession } from "@/lib/api/kb-sessions";

interface KBSessionFieldListProps {
  session: KBCreationSession;
  onSuggest: (fieldKey: string) => void;
  onAnswer: (fieldKey: string, value: string) => void;
  onAcceptSuggestion: (fieldKey: string, value: string) => void;
  onRejectSuggestion: (fieldKey: string) => void;
  onStartInterview: () => void;
  onEnhance: () => void;
  suggestingFieldKey?: string | null;
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
}: KBSessionFieldListProps) {
  const t = useTranslations("studio");
  const [editingFieldKey, setEditingFieldKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  // Calculate progress
  const totalFields = session.fields.length;
  const filledFields = session.fields.filter(
    (f) => f.final_value || f.user_value || f.ai_suggested_value,
  ).length;

  // Group fields
  const emptyFields = session.fields.filter(
    (f) => !f.final_value && !f.user_value && !f.ai_suggested_value,
  );
  const userFields = session.fields.filter(
    (f) => (f.user_value || f.final_value) && f.source === "user",
  );
  const aiFields = session.fields.filter((f) => f.ai_suggested_value && f.source === "ai");
  const mergedFields = session.fields.filter(
    (f) => f.source === "merged" || f.source === "world_derived",
  );

  function startEdit(field: KBCreationField) {
    setEditingFieldKey(field.field_key);
    setEditValue(field.final_value || field.user_value || "");
  }

  function saveEdit(fieldKey: string) {
    if (editValue.trim()) {
      onAnswer(fieldKey, editValue.trim());
    }
    setEditingFieldKey(null);
    setEditValue("");
  }

  function cancelEdit() {
    setEditingFieldKey(null);
    setEditValue("");
  }

  // Source badge component
  function SourceBadge({ source }: { source: KBCreationField["source"] }) {
    const badges: Record<KBCreationField["source"], { label: string; className: string }> = {
      user: {
        label: t("kb.source_user"),
        className: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
      },
      ai: {
        label: t("kb.source_ai"),
        className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
      },
      world_derived: {
        label: t("kb.source_world_derived"),
        className: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
      },
      merged: {
        label: t("kb.source_merged"),
        className: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
      },
    };
    const badge = badges[source];
    return (
      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${badge.className}`}>
        {badge.label}
      </span>
    );
  }

  // Individual field renderer
  function FieldRow({ field, isEmpty = false }: { field: KBCreationField; isEmpty?: boolean }) {
    const isEditing = editingFieldKey === field.field_key;
    const isSuggesting = suggestingFieldKey === field.field_key;
    const displayValue = field.final_value || field.user_value || field.ai_suggested_value || "";
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Focus textarea when editing starts
    useEffect(() => {
      if (isEditing && textareaRef.current) {
        textareaRef.current.focus();
      }
    }, [isEditing]);

    return (
      <div key={field.field_key} className="p-3 border border-border rounded-lg bg-card">
        {/* Field header */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="text-sm font-medium">{field.label}</div>
            {field.required && <span className="text-red-500">*</span>}
            {!isEmpty && <SourceBadge source={field.source} />}
          </div>
          <div className="flex items-center gap-1">
            {isEmpty && (
              <button
                type="button"
                onClick={() => onSuggest(field.field_key)}
                disabled={isSuggesting}
                className="flex items-center gap-1 px-2 py-1 text-xs text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/30 rounded-md transition-colors disabled:opacity-50"
              >
                <Sparkles className="w-3 h-3" />
                {t("kb.suggestAI")}
              </button>
            )}
            {!isEmpty && !isEditing && (
              <button
                type="button"
                onClick={() => startEdit(field)}
                className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors"
              >
                <Edit3 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Field content */}
        {isEditing ? (
          <div className="space-y-2">
            <textarea
              ref={textareaRef}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              placeholder={`Enter ${field.label.toLowerCase()}...`}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm min-h-[80px] resize-y"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={cancelEdit}
                className="flex items-center gap-1 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors"
              >
                <X className="w-3 h-3" />
                {t("kb.cancel")}
              </button>
              <button
                type="button"
                onClick={() => saveEdit(field.field_key)}
                disabled={!editValue.trim()}
                className="flex items-center gap-1 px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                <Check className="w-3 h-3" />
                {t("kb.save")}
              </button>
            </div>
          </div>
        ) : isEmpty ? (
          <textarea
            placeholder={`Enter ${field.label.toLowerCase()}...`}
            className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm min-h-[60px] resize-y focus:outline-none focus:ring-2 focus:ring-primary/50"
            onBlur={(e) => {
              if (e.target.value.trim()) {
                onAnswer(field.field_key, e.target.value.trim());
                e.target.value = "";
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                const target = e.target as HTMLTextAreaElement;
                if (target.value.trim()) {
                  onAnswer(field.field_key, target.value.trim());
                  target.value = "";
                }
              }
            }}
          />
        ) : field.ai_suggested_value && field.source === "ai" && !field.final_value ? (
          // AI suggestion pending review
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
                {t("kb.reject")}
              </button>
              <button
                type="button"
                onClick={() => onAcceptSuggestion(field.field_key, field.ai_suggested_value!)}
                className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
              >
                <Check className="w-3 h-3" />
                {t("kb.accept")}
              </button>
            </div>
          </div>
        ) : (
          // Display filled value
          <div className="text-sm text-muted-foreground whitespace-pre-wrap">{displayValue}</div>
        )}
      </div>
    );
  }

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
          <div>
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
              {t("kb.toFill") || "To Fill"} ({emptyFields.length})
            </h4>
            <div className="space-y-2">
              {emptyFields.map((field) => (
                <FieldRow key={field.field_key} field={field} isEmpty />
              ))}
            </div>
          </div>
        )}

        {/* AI suggestions pending review */}
        {aiFields.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-green-600 dark:text-green-400 uppercase tracking-wider mb-2">
              {t("kb.aiSuggestions") || "AI Suggestions"} ({aiFields.length})
            </h4>
            <div className="space-y-2">
              {aiFields.map((field) => (
                <FieldRow key={field.field_key} field={field} />
              ))}
            </div>
          </div>
        )}

        {/* User-filled fields */}
        {userFields.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase tracking-wider mb-2">
              {t("kb.completed") || "Completed"} ({userFields.length})
            </h4>
            <div className="space-y-2">
              {userFields.map((field) => (
                <FieldRow key={field.field_key} field={field} />
              ))}
            </div>
          </div>
        )}

        {/* Merged / world-derived fields */}
        {mergedFields.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-purple-600 dark:text-purple-400 uppercase tracking-wider mb-2">
              {t("kb.fromStory") || "From Story"} ({mergedFields.length})
            </h4>
            <div className="space-y-2">
              {mergedFields.map((field) => (
                <FieldRow key={field.field_key} field={field} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
