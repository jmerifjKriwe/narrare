"use client";

/**
 * PromptEditorViewMode — read-only prompt template view.
 *
 * After PROMPT-003, the local ``Preview/Edit`` toggle and the embedded
 * :component:`PromptPreview` (EXAMPLE_VALUES substitution) are gone. The
 * raw template is shown directly; preview happens in the API-driven
 * :component:`PromptPreviewDialog` triggered by the parent.
 */

import { useTranslations } from "next-intl";

interface PromptEditorViewModeProps {
  readonly content: string;
  readonly isOverridden: boolean;
  readonly variables: readonly string[];
  readonly onStartEdit: () => void;
  readonly onOpenPreview: () => void;
  readonly onOpenLiveTest: () => void;
  readonly onOpenReset: () => void;
  readonly isResetPending: boolean;
}

/** Read-only prompt template view with edit / preview / live-test / reset actions. */
export function PromptEditorViewMode({
  content,
  isOverridden,
  onStartEdit,
  onOpenPreview,
  onOpenLiveTest,
  onOpenReset,
  isResetPending,
}: PromptEditorViewModeProps) {
  const t = useTranslations("studio");

  return (
    <>
      <div className="flex items-center justify-between">
        <label htmlFor="prompt-viewer" className="block text-sm font-medium">
          {isOverridden ? t("settings.prompts.promptContent") : t("settings.prompts.baseContent")}
        </label>
      </div>
      <pre
        id="prompt-viewer"
        className="w-full min-h-[400px] px-4 py-3 border border-border rounded-md bg-background text-sm font-mono whitespace-pre-wrap overflow-auto"
      >
        {content}
      </pre>
      <div className="flex flex-wrap justify-end gap-3">
        <button
          type="button"
          onClick={onOpenPreview}
          className="px-4 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
        >
          {t("settings.prompts.promptCustomization.preview")}
        </button>
        <button
          type="button"
          onClick={onOpenLiveTest}
          className="px-4 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
        >
          {t("settings.prompts.promptCustomization.test")}
        </button>
        <button
          type="button"
          onClick={onOpenReset}
          disabled={isResetPending || !isOverridden}
          className="px-4 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm disabled:opacity-50"
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
