"use client";

import { Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";
import { cn, estimateReadingTime, formatWordCount } from "@/lib/utils";
import type { Chapter } from "@/types";

interface StatusBarProps {
  chapter: Chapter | null;
}

const SAVE_STATUS_COLORS: Record<string, string> = {
  idle: "text-transparent",
  saving: "text-primary",
  saved: "text-green-600 dark:text-green-400",
  error: "text-destructive",
};

/** Strip HTML tags to get plain text for character count. */
function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, "");
}

export function StatusBar({ chapter }: StatusBarProps) {
  const t = useTranslations("editor");
  const { saveStatus } = useEditorStore();

  const wordCount = chapter?.word_count ?? 0;
  const plainText = chapter?.content ? stripHtml(chapter.content) : "";
  const charCount = plainText.length;
  const readingTime = estimateReadingTime(wordCount);

  const saveLabel = t(`saveStatus.${saveStatus}`);

  return (
    <div
      className="border-t border-border/40 px-10 py-2.5 bg-background shrink-0"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center justify-between text-[0.6875rem] font-medium tracking-tight">
        <div className="flex items-center gap-6 text-muted-foreground/50">
          {chapter && (
            <>
              <span className="hover:text-muted-foreground transition-colors cursor-default">
                {t("wordCount", { count: formatWordCount(wordCount) })}
              </span>
              <span className="opacity-30">·</span>
              <span className="hover:text-muted-foreground transition-colors cursor-default">
                {t("charCount", { count: formatWordCount(charCount) })}
              </span>
              <span className="opacity-30">·</span>
              <span className="hover:text-muted-foreground transition-colors cursor-default">
                {t("readingTime", { time: readingTime })}
              </span>
            </>
          )}
        </div>

        <div className="flex items-center gap-6">
          {/* Save status */}
          {saveLabel && (
            <span
              className={cn("flex items-center gap-1.5 uppercase tracking-[0.05em] text-[10px]", SAVE_STATUS_COLORS[saveStatus])}
              role="status"
              aria-label={`Save status: ${saveStatus}`}
            >
              {saveStatus === "saving" && (
                <span
                  className="w-2 h-2 border-1.5 border-current border-t-transparent rounded-full animate-spin inline-block"
                  aria-hidden="true"
                />
              )}
              {saveLabel}
            </span>
          )}

          {/* AI active indicator — always visible for now */}
          <div className="flex items-center gap-1.5 text-muted-foreground/40 hover:text-muted-foreground transition-colors cursor-default">
            <Sparkles className="w-3 h-3" aria-hidden="true" />
            <span className="uppercase tracking-[0.05em] text-[10px] font-bold">{t("aiActive")}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
