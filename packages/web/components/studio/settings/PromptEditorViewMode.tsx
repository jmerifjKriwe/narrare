"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { PromptPreview } from "./PromptPreview";

// --- Types ---

interface PromptEditorViewModeProps {
  readonly content: string;
  readonly isOverridden: boolean;
  readonly variables: readonly string[];
  readonly previewMode: boolean;
  readonly onSetPreviewMode: (mode: boolean) => void;
  readonly onStartEdit: () => void;
  readonly onReset: () => void;
  readonly isResetPending: boolean;
}

// --- Component ---

/** Read-only prompt view with edit/preview toggle and action buttons. */
export function PromptEditorViewMode({
  content,
  isOverridden,
  variables,
  previewMode,
  onSetPreviewMode,
  onStartEdit,
  onReset,
  isResetPending,
}: PromptEditorViewModeProps) {
  const t = useTranslations("studio");

  return (
    <>
      <div className="flex items-center justify-between">
        <label htmlFor="prompt-viewer" className="block text-sm font-medium">
          {isOverridden ? t("settings.prompts.promptContent") : t("settings.prompts.baseContent")}
        </label>
        {/* Preview / Edit toggle */}
        {variables.length > 0 && (
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => onSetPreviewMode(false)}
              className={cn(
                "px-3 py-1 rounded-full text-xs font-medium transition-colors",
                !previewMode
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-muted text-muted-foreground hover:bg-accent",
              )}
            >
              {t("settings.prompts.edit")}
            </button>
            <button
              type="button"
              onClick={() => onSetPreviewMode(true)}
              className={cn(
                "px-3 py-1 rounded-full text-xs font-medium transition-colors",
                previewMode
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-muted text-muted-foreground hover:bg-accent",
              )}
            >
              {t("settings.prompts.preview")}
            </button>
          </div>
        )}
      </div>
      {previewMode ? (
        <PromptPreview content={content} variables={variables} />
      ) : (
        <div className="w-full min-h-[400px] px-4 py-3 border border-border rounded-md bg-background text-sm font-mono whitespace-pre-wrap overflow-auto">
          {content}
        </div>
      )}
      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={onReset}
          disabled={isResetPending || !isOverridden}
          className="px-6 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm disabled:opacity-50"
        >
          {isResetPending ? t("settings.ai.loading") : t("settings.prompts.resetToDefault")}
        </button>
        <button
          type="button"
          onClick={onStartEdit}
          className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm"
        >
          {t("settings.prompts.editOverride")}
        </button>
      </div>
    </>
  );
}
