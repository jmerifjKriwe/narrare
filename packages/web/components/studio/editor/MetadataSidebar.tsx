"use client";

import { useLocale, useTranslations } from "next-intl";
import { formatWordCount } from "@/lib/utils";
import type { Chapter, ChapterSummary } from "@/types";

interface MetadataSidebarProps {
  /** Live word count from editor content */
  wordCount: number;
  /** Live character count from editor content */
  charCount: number;
  /** Live paragraph count from editor content */
  paragraphCount: number;
  /** Current chapter data from API */
  chapter: Chapter | null;
  /** All chapters for novel (for total count + position) */
  chapters: ChapterSummary[];
  /** Word count when chapter was first loaded (for session delta) */
  sessionStartWordCount: number;
}

const WRITING_GOAL = 80_000;

const statusColors: Record<string, string> = {
  draft: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  reviewed: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  final: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
};

export function MetadataSidebar({
  wordCount,
  charCount,
  paragraphCount,
  chapter,
  chapters,
  sessionStartWordCount,
}: MetadataSidebarProps) {
  const t = useTranslations("studio");
  const locale = useLocale();

  const readingTime = Math.ceil(wordCount / 250);
  const sessionDelta = wordCount - sessionStartWordCount;
  const totalWords = chapters.reduce((sum, c) => sum + c.word_count, 0);
  const progressPercent = Math.min(Math.round((totalWords / WRITING_GOAL) * 100), 100);
  const chapterPosition = chapter ? chapters.findIndex((c) => c.id === chapter.id) + 1 : 0;

  const fmt = (n: number) => formatWordCount(n, locale);

  return (
    <div className="w-64 bg-card border-l border-border overflow-y-auto flex-shrink-0">
      {/* Statistics */}
      <div className="border-b border-border">
        <SectionHeader>{t("metadataSidebar.statistics")}</SectionHeader>
        <div className="px-4 py-3 space-y-2">
          <StatRow label={t("metadataSidebar.words")} value={fmt(wordCount)} />
          <StatRow label={t("metadataSidebar.characters")} value={fmt(charCount)} />
          <StatRow
            label={t("metadataSidebar.readingTime")}
            value={t("metadataSidebar.readingTimeValue", { minutes: readingTime })}
          />
          <StatRow label={t("metadataSidebar.paragraphs")} value={String(paragraphCount)} />
        </div>
      </div>

      {/* Session */}
      <div className="border-b border-border">
        <SectionHeader>{t("metadataSidebar.session")}</SectionHeader>
        <div className="px-4 py-3">
          <SessionDelta delta={sessionDelta} />
          <p className="text-xs text-muted-foreground mt-1">
            {t("metadataSidebar.sessionStart", { count: fmt(sessionStartWordCount) })}
          </p>
        </div>
      </div>

      {/* Chapter Info */}
      <div className="border-b border-border">
        <SectionHeader>{t("metadataSidebar.chapterInfo")}</SectionHeader>
        <div className="px-4 py-3 space-y-2">
          {chapter ? (
            <>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{t("metadataSidebar.status")}</span>
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[chapter.status] ?? ""}`}
                >
                  {chapter.status}
                </span>
              </div>
              <StatRow
                label={t("metadataSidebar.povCharacter")}
                value={chapter.pov_character_id || t("metadataSidebar.noPov")}
              />
              <StatRow
                label={t("metadataSidebar.timelinePosition")}
                value={chapter.timeline_position || t("metadataSidebar.noTimeline")}
              />
              <StatRow
                label={t("metadataSidebar.chapterPosition")}
                value={
                  chapters.length > 0
                    ? t("metadataSidebar.chapterPosition", {
                        current: chapterPosition,
                        total: chapters.length,
                      })
                    : "\u2014"
                }
              />
            </>
          ) : (
            <p className="text-xs text-muted-foreground">{t("editor.selectChapter")}</p>
          )}
        </div>
      </div>

      {/* Novel Progress */}
      <div>
        <SectionHeader>{t("metadataSidebar.novelProgress")}</SectionHeader>
        <div className="px-4 py-3 space-y-2">
          <StatRow label={t("metadataSidebar.totalWords")} value={fmt(totalWords)} />
          <div className="w-full bg-muted rounded-full h-2">
            <div
              className="bg-primary h-2 rounded-full transition-all duration-300"
              // Dynamic percentage width requires inline style
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground text-center">
            {t("metadataSidebar.progressLabel", {
              current: fmt(totalWords),
              goal: fmt(WRITING_GOAL),
              percent: progressPercent,
            })}
          </p>
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs text-muted-foreground uppercase tracking-wider px-4 py-2">{children}</h3>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-foreground">{value}</span>
    </div>
  );
}

function SessionDelta({ delta }: { delta: number }) {
  const t = useTranslations("studio");

  if (delta > 0) {
    return (
      <p className="text-sm text-green-600 dark:text-green-400 font-medium">
        {t("metadataSidebar.sessionDelta", { count: delta })}
      </p>
    );
  }
  if (delta < 0) {
    return (
      <p className="text-sm text-red-600 dark:text-red-400 font-medium">
        {t("metadataSidebar.sessionDeltaNegative", { count: delta })}
      </p>
    );
  }
  return (
    <p className="text-sm text-muted-foreground">
      {t("metadataSidebar.sessionDelta", { count: 0 })}
    </p>
  );
}
