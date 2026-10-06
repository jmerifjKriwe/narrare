"use client";

/**
 * CostTotalsCard — headline totals for one month (STATS-002, ADR-093 §5).
 *
 * Extracted from AnalyticsCostsPanel to keep it under the RULE-04 limit.
 * Four stat blocks (calls, tokens in/out, cost USD) via next-intl
 * `useFormatter().number` (locale-aware separators, USD currency), plus the
 * unpriced-calls warning badge, rendered iff `unpriced_calls > 0`.
 */

import { useFormatter, useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import type { CostTotals } from "@/lib/api/analytics";

interface CostTotalsCardProps {
  readonly totals: CostTotals;
}

export function CostTotalsCard({ totals }: CostTotalsCardProps) {
  const t = useTranslations("analytics.costs");
  const format = useFormatter();
  const usd = (value: number) => format.number(value, { style: "currency", currency: "USD" });
  const stats: Array<[string, string]> = [
    [t("calls"), format.number(totals.calls)],
    [t("tokensIn"), format.number(totals.tokens_in)],
    [t("tokensOut"), format.number(totals.tokens_out)],
    [t("cost"), usd(totals.cost_usd)],
  ];

  return (
    <>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xl font-medium">{t("title")}</h2>
        {totals.unpriced_calls > 0 && (
          <Badge
            variant="outline"
            data-testid="costs-unpriced-badge"
            className="rounded-full border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400"
          >
            {t("unpriced", { count: totals.unpriced_calls })}
          </Badge>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-border bg-card p-3">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p>
            <p className="mt-1 font-mono text-lg font-medium tabular-nums">{value}</p>
          </div>
        ))}
      </div>
    </>
  );
}
