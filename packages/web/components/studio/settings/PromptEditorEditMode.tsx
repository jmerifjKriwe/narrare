"use client";

import { useTranslations } from "next-intl";

// --- Types ---

interface PromptEditorEditModeProps {
  readonly editedContent: string;
  readonly onContentChange: (value: string) => void;
  readonly onSave: () => void;
  readonly onCancel: () => void;
  readonly isSavePending: boolean;
}

// --- Component ---

/** Edit mode for prompt content with textarea and save/cancel actions. */
export function PromptEditorEditMode({
  editedContent,
  onContentChange,
  onSave,
  onCancel,
  isSavePending,
}: PromptEditorEditModeProps) {
  const t = useTranslations("studio");

  return (
    <>
      <label htmlFor="prompt-editor" className="block text-sm font-medium">
        {t("settings.prompts.promptContent")}
      </label>
      <textarea
        id="prompt-editor"
        value={editedContent}
        onChange={(e) => onContentChange(e.target.value)}
        className="w-full min-h-[400px] px-4 py-3 border border-border rounded-md bg-background text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-ring/15"
      />
      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="px-6 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
        >
          {t("settings.prompts.cancel")}
        </button>
        <button
          type="button"
          onClick={onSave}
          disabled={isSavePending}
          className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
        >
          {isSavePending ? t("settings.ai.loading") : t("settings.prompts.saveOverride")}
        </button>
      </div>
    </>
  );
}
