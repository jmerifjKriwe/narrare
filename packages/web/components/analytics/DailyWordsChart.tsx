"use client";

/**
 * DailyWordsChart — 90-day daily-words bar chart (STATS-001, spec E-6).
 *
 * Extracted from WritingStatsPanel to keep it under the RULE-04 soft target
 * (mirrors the CostsPanel → CostTrendChart split). Recharts BarChart per the
 * SentimentChart pattern: ResponsiveContainer, design-token
 * `hsl(var(--primary))` bars, muted ticks, accent cursor, locale-formatted
 * word-count axis + tooltip; exposed as `role="img"` with an aria-label.
 * 90 daily `YYYY-MM-DD` ticks would overlap, so the X axis thins to ~8
 * evenly spaced ticks rendered as `MM-DD` (year is implied by the window).
 */

import { useFormatter, useTranslations } from "next-intl";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DailyPoint } from "@/lib/api/analytics";

interface DailyWordsChartProps {
  /** Zero-filled UTC days, oldest first (report window). */
  readonly dailies: DailyPoint[];
}

export function DailyWordsChart({ dailies }: DailyWordsChartProps) {
  const t = useTranslations("analytics.writing");
  const format = useFormatter();
  // Recharts `interval={n}` renders a tick every (n+1)-th point → for the
  // 90-day window this yields ~8 date labels; guards a short/empty window.
  const tickInterval = Math.max(0, Math.ceil(dailies.length / 8) - 1);

  return (
    <div
      role="img"
      aria-label={t("chart")}
      className="w-full rounded-lg border border-border bg-card p-3"
    >
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={dailies} margin={{ left: 0, right: 8, top: 4, bottom: 4 }}>
          <XAxis
            dataKey="date"
            interval={tickInterval}
            tickFormatter={(value: string) => value.slice(5)}
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          />
          <YAxis
            width={56}
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(value: number) => format.number(value)}
          />
          <Tooltip
            formatter={(value) => format.number(Number(value))}
            cursor={{ fill: "hsl(var(--accent))" }}
          />
          <Bar dataKey="words" fill="hsl(var(--primary))" radius={[2, 2, 0, 0]} maxBarSize={8} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
