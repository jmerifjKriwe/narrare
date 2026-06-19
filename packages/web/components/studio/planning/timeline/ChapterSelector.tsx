"use client";

import { Loader2, StopCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChapterSummary {
  readonly id: string;
  readonly title: string;
}

interface ChapterSelectorProps {
  readonly chapters: ChapterSummary[];
  readonly chaptersLoaded: boolean;
  readonly chaptersError: boolean;
  readonly selectedChapterIds: Set<string>;
  readonly isExtracting: boolean;
  readonly extractError: string | null;
  readonly onToggleChapter: (chapterId: string) => void;
  readonly onExtract: () => void;
  /** Cancel an in-flight extraction (§16.2 visible cancel). */
  readonly onCancel?: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Chapter picker and extraction trigger for timeline SSE extraction. */
export function ChapterSelector({
  chapters,
  chaptersLoaded,
  chaptersError,
  selectedChapterIds,
  isExtracting,
  extractError,
  onToggleChapter,
  onExtract,
  onCancel,
}: ChapterSelectorProps) {
  const t = useTranslations("timeline");
  const tAction = useTranslations("studio.aiActions");
  const hasSelection = selectedChapterIds.size > 0;

  return (
    <div className="px-4 py-3 border-b border-border">
      <p className="text-xs font-medium text-muted-foreground mb-2">{t("selectChapters")}</p>

      {chaptersError ? (
        <p className="text-xs text-[var(--color-error)]">{t("errorLoading")}</p>
      ) : chapters.length === 0 && chaptersLoaded ? (
        <p className="text-xs text-muted-foreground">{t("noEvents")}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {chapters.map((chapter) => (
            <label
              key={chapter.id}
              className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md border cursor-pointer transition-colors",
                selectedChapterIds.has(chapter.id)
                  ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                  : "border-border bg-card text-muted-foreground hover:bg-[var(--color-bg-secondary)]",
              )}
            >
              <input
                type="checkbox"
                checked={selectedChapterIds.has(chapter.id)}
                onChange={() => onToggleChapter(chapter.id)}
                className="sr-only"
              />
              {chapter.title}
            </label>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={onExtract}
        disabled={!hasSelection || isExtracting}
        className="mt-3 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
      >
        {isExtracting ? (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            {t("extracting")}
          </>
        ) : (
          t("extractButton")
        )}
      </button>

      {/* Visible cancel control while extraction is in flight (§16.2 / CR-AUFG-07-09) */}
      {isExtracting && onCancel && (
        <button
          type="button"
          onClick={onCancel}
          data-testid="timeline-extract-stop"
          aria-label={tAction("stop")}
          className="mt-2 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-border text-foreground hover:bg-[var(--color-bg-secondary)] transition-colors"
        >
          <StopCircle className="w-3.5 h-3.5" />
          {tAction("stop")}
        </button>
      )}

      {extractError && <p className="text-xs text-[var(--color-error)] mt-2">{extractError}</p>}
    </div>
  );
}
