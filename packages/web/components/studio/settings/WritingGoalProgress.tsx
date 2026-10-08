"use client";

/**
 * WritingGoalProgress — read-only progress display for the persisted writing
 * goal: progress label + word count + bar. Extracted from WritingGoalsTab
 * (RULE-04); pure display — all goal state (draft, stored target) stays in
 * the tab and is passed in.
 */

import { useTranslations } from "next-intl";

interface WritingGoalProgressProps {
  /** Total words across the novel's chapters. */
  currentWords: number;
  /** Target the user sees: the valid draft while editing, else the stored goal. */
  target: number | null;
}

export function WritingGoalProgress({ currentWords, target }: WritingGoalProgressProps) {
  const t = useTranslations("studio");

  // Targets ≤ 0 show no bar (the backend likewise treats non-positive
  // targets as "no goal").
  const progressPercent =
    target !== null && target > 0 ? Math.min(Math.round((currentWords / target) * 100), 100) : null;

  return (
    <>
      <div className="flex items-center justify-between mb-2 mt-4">
        <span className="text-sm text-muted-foreground">{t("settings.writing.progress")}</span>
        <span className="text-sm font-medium">
          {progressPercent === null
            ? currentWords.toLocaleString()
            : `${currentWords.toLocaleString()} / ${target?.toLocaleString()} (${progressPercent}%)`}
        </span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-primary rounded-full transition-all"
          style={{ width: `${progressPercent ?? 0}%` }}
        />
      </div>
    </>
  );
}
