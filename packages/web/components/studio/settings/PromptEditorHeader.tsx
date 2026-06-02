"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

// --- Types ---

interface StatusMessage {
  readonly type: "success" | "error";
  readonly text: string;
}

interface PromptEditorHeaderProps {
  readonly promptId: string;
  readonly isOverridden: boolean;
  readonly hasUpdate: boolean;
  readonly statusMessage: StatusMessage | null;
  readonly onBack: () => void;
  readonly onShowDiff: () => void;
}

// --- Component ---

/** Prompt editor header with back navigation, source badge, and status messages. */
export function PromptEditorHeader({
  promptId,
  isOverridden,
  hasUpdate,
  statusMessage,
  onBack,
  onShowDiff,
}: PromptEditorHeaderProps) {
  const t = useTranslations("studio");

  return (
    <>
      {/* Back navigation + title */}
      <div className="mb-6">
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
        >
          {t("settings.prompts.back")}
        </button>
        <h2 className="text-xl font-medium">{promptId}</h2>
      </div>

      {/* Source indicator, update badge, and status */}
      <div className="space-y-4 mb-4">
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold",
              isOverridden ? "bg-accent text-accent-foreground" : "bg-muted text-muted-foreground",
            )}
          >
            {isOverridden
              ? t("settings.prompts.sourceOverride")
              : t("settings.prompts.sourceBundled")}
          </span>
          {hasUpdate && (
            <button
              type="button"
              onClick={onShowDiff}
              className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-colors"
            >
              {t("settings.prompts.updateAvailable")}
            </button>
          )}
        </div>

        {statusMessage && (
          <div
            className={cn(
              "rounded-md p-3 text-sm",
              statusMessage.type === "success"
                ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                : "bg-destructive/10 text-destructive",
            )}
            role="status"
          >
            {statusMessage.text}
          </div>
        )}
      </div>
    </>
  );
}
