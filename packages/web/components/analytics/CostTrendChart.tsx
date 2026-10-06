"use client";

/**
 * CostTrendChart — six-month AI cost trend (STATS-002, ADR-093 §5).
 *
 * Extracted from AnalyticsCostsPanel to keep it under the RULE-04 limit.
 * Recharts BarChart per the SentimentChart pattern: ResponsiveContainer,
 * design-token `hsl(var(--primary))` bars, muted ticks, accent cursor, USD
 * axis + tooltip formatting; exposed as `role="img"` with an aria-label.
 */

import { useFormatter, useTranslations } from "next-intl";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CostTrendPoint } from "@/lib/api/analytics";

interface CostTrendChartProps {
  readonly trend: CostTrendPoint[];
}

export function CostTrendChart({ trend }: CostTrendChartProps) {
  const t = useTranslations("analytics.costs");
  const format = useFormatter();
  const usd = (value: number) => format.number(value, { style: "currency", currency: "USD" });

  return (
    <div
      role="img"
      aria-label={t("trend")}
      className="w-full rounded-lg border border-border bg-card p-3"
    >
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={trend} margin={{ left: 0, right: 8, top: 4, bottom: 4 }}>
          <XAxis dataKey="month" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
          <YAxis
            width={64}
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(value: number) => usd(value)}
          />
          <Tooltip
            formatter={(value) => usd(Number(value))}
            cursor={{ fill: "hsl(var(--accent))" }}
          />
          <Bar
            dataKey="cost_usd"
            fill="hsl(var(--primary))"
            radius={[4, 4, 0, 0]}
            maxBarSize={32}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
