"use client";

import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";
import { cn, estimateReadingTime, formatWordCount } from "@/lib/utils";
import type { Chapter } from "@/types";

interface StatusBarProps {
  chapter: Chapter | null;
}

const SAVE_STATUS_COLORS: Record<string, string> = {
  idle: "text-transparent",
  saving: "text-[var(--color-text-secondary)]",
  saved: "text-[var(--color-success)]",
  error: "text-[var(--color-error)]",
};

export function StatusBar({ chapter }: StatusBarProps) {
  const t = useTranslations("editor");
  const { saveStatus } = useEditorStore();

  const wordCount = chapter?.word_count ?? 0;
  const readingTime = estimateReadingTime(wordCount);

  const saveLabel = t(`saveStatus.${saveStatus}`);

  return (
    <div
      className="h-7 border-t border-[var(--color-border)] bg-[var(--color-surface)] flex items-center justify-between px-4 shrink-0"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2">
        {chapter && (
          <>
            <span className="text-xs text-[var(--color-text-tertiary)]">
              {t("wordCount", { count: formatWordCount(wordCount) })}
            </span>
            <span className="text-[var(--color-text-tertiary)] text-xs">·</span>
            <span className="text-xs text-[var(--color-text-tertiary)]">
              {t("readingTime", { time: readingTime })}
            </span>
          </>
        )}
      </div>

      <div className="flex items-center gap-2">
        {saveLabel && (
          <span
            className={cn("text-xs flex items-center gap-1", SAVE_STATUS_COLORS[saveStatus])}
            role="status"
            aria-label={`Save status: ${saveStatus}`}
          >
            {saveStatus === "saving" && (
              <span
                className="w-2 h-2 border-1.5 border-current border-t-transparent rounded-full animate-spin inline-block"
                aria-hidden="true"
              />
            )}
            {saveStatus === "error" && (
              <span
                className="w-1.5 h-1.5 rounded-full bg-[var(--color-error)]"
                aria-hidden="true"
              />
            )}
            {saveStatus === "saved" && (
              <span
                className="w-1.5 h-1.5 rounded-full bg-[var(--color-success)]"
                aria-hidden="true"
              />
            )}
            {saveLabel}
          </span>
        )}
      </div>
    </div>
  );
}
