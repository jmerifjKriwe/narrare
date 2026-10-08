"use client";

/**
 * WritingStatsPanel — writing-activity report (STATS-001, spec E-6).
 *
 * Self-contained second analytics tab: novel scope selector (optional —
 * "All novels" default + the user's novels via `useNovels`, the same list
 * hook sibling pickers read), summary cards (today's words, current/longest
 * streak, total words), the novel goal progress bar when the report carries
 * a goal block (novel-scoped + target set), and the 90-day daily-words bar
 * chart (DailyWordsChart, RULE-04 split — mirrors CostsPanel → CostTrendChart).
 *
 * Data via `useAnalyticsWriting(novelId)`; `keepPreviousData` keeps the
 * previous scope's report mounted while a selector switch refetches. The
 * empty state fires only when the scope has NO recorded activity at all —
 * the all-time total plus the longest streak also cover activity outside
 * the 90-day window and net-zero write/delete days. A freshly set goal on
 * an untouched novel still renders its progress bar above the empty
 * message (the onboarding moment must not hide the goal). Strings via
 * `analytics.writing.*`.
 */

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { StatusMessage } from "@/components/ui/status-message";
import type { WritingReport } from "@/lib/api/analytics";
import type { GoalBlock } from "@/lib/hooks/useAnalyticsWriting";
import { useAnalyticsWriting } from "@/lib/hooks/useAnalyticsWriting";
import { useNovels } from "@/lib/hooks/useNovels";
import { DailyWordsChart } from "./DailyWordsChart";

/** True only when the scope has no recorded writing activity at all. */
function hasNoActivity(report: WritingReport): boolean {
  return (
    report.total_words === 0 &&
    report.today_words === 0 &&
    report.streaks.longest === 0 &&
    report.streaks.current === 0
  );
}

/** Today / current streak / longest streak / total — stat-block grid. */
function WritingSummaryCards({ report }: { readonly report: WritingReport }) {
  const t = useTranslations("analytics.writing");
  const format = useFormatter();
  // ICU plural renders count + unit in one locale-correct string ("4 days").
  const days = (count: number) => t("streakDays", { count });
  const stats: Array<[string, string]> = [
    [t("today"), format.number(report.today_words)],
    [t("streakCurrent"), days(report.streaks.current)],
    [t("streakLongest"), days(report.streaks.longest)],
    [t("totalWords"), format.number(report.total_words)],
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {stats.map(([label, value]) => (
        <div key={label} className="rounded-lg border border-border bg-card p-3">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p>
          <p className="mt-1 font-mono text-lg font-medium tabular-nums">{value}</p>
        </div>
      ))}
    </div>
  );
}

/**
 * Novel goal progress (spec E-4: target vs LIVE manuscript words, so the
 * percentage can exceed the activity-based numbers) — track + labelled
 * percentage. `progress_pct` is clamped defensively for the bar geometry.
 */
function WritingGoalProgress({ goal }: { readonly goal: GoalBlock }) {
  const t = useTranslations("analytics.writing");
  const format = useFormatter();
  const pct = Math.min(100, Math.max(0, goal.progress_pct));

  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="font-medium">{t("goalTitle")}</span>
        <span className="font-mono text-xs tabular-nums text-muted-foreground">
          {t("goalOf", {
            current: format.number(goal.current_words),
            target: format.number(goal.target_words),
            percent: format.number(goal.progress_pct),
          })}
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={t("goalTitle")}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted"
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** Fetches the scoped report and renders its states + sub-components. */
function WritingReportView({ novelId }: { readonly novelId: string | null }) {
  const t = useTranslations("analytics.writing");
  const { data, isPending, isError, refetch } = useAnalyticsWriting(novelId);

  if (isPending) return <StatusMessage state="loading" />;

  if (isError || !data) {
    return (
      <StatusMessage
        state="error"
        message={t("error")}
        action={
          <button
            type="button"
            onClick={() => refetch()}
            className="rounded-md border border-border px-2 py-1 text-xs font-medium hover:bg-accent"
          >
            {t("retry")}
          </button>
        }
      />
    );
  }

  // E7 review: a just-set goal on a brand-new novel is exactly the empty
  // state (zero activity) — surface the goal bar above the empty message so
  // the onboarding moment shows the user's goal instead of hiding it.
  if (hasNoActivity(data)) {
    return (
      <div className="flex flex-col gap-6">
        {data.goal && <WritingGoalProgress goal={data.goal} />}
        <StatusMessage state="empty" message={t("empty")} />
      </div>
    );
  }

  return (
    <>
      <WritingSummaryCards report={data} />
      {data.goal && <WritingGoalProgress goal={data.goal} />}
      <DailyWordsChart dailies={data.dailies} />
    </>
  );
}

/** Writing-activity report: novel scope selector + stats + 90-day chart. */
export function WritingStatsPanel() {
  const t = useTranslations("analytics.writing");
  const { data: novels = [] } = useNovels();
  // null = "All novels" (no novel_id query param — the hook's default scope).
  const [novelId, setNovelId] = useState<string | null>(null);

  return (
    <section className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xl font-medium">{t("title")}</h2>
        <label className="flex items-center gap-1.5 text-sm font-normal text-muted-foreground">
          <span>{t("novelLabel")}</span>
          <select
            data-testid="writing-novel-select"
            aria-label={t("novelLabel")}
            value={novelId ?? ""}
            onChange={(event) => setNovelId(event.target.value || null)}
            className="cursor-pointer rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">{t("novelAll")}</option>
            {novels.map((novel) => (
              <option key={novel.id} value={novel.id}>
                {novel.title}
              </option>
            ))}
          </select>
        </label>
      </div>
      <WritingReportView novelId={novelId} />
    </section>
  );
}
