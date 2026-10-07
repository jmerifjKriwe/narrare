"use client";

/**
 * CostTotalsCard — headline totals for one month (STATS-002, ADR-093 §5).
 *
 * Extracted from AnalyticsCostsPanel to keep it under the RULE-04 limit.
 * Four stat blocks (calls, tokens in/out, cost USD) via next-intl
 * `useFormatter().number` (locale-aware separators, USD currency), the
 * unpriced-calls warning badge (iff `unpriced_calls > 0`) and the budget
 * badge (STATS-002 budgets, ADR-094: neutral OK percentage, amber warn over
 * budget, destructive "AI blocked" in block mode).
 */

import { useFormatter, useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import type { CostBudgetBlock, CostTotals } from "@/lib/api/analytics";

interface CostTotalsCardProps {
  readonly totals: CostTotals;
  /** Budget overlay from the report; null when the user set no budget. */
  readonly budget: CostBudgetBlock | null;
}

/** Percentage of the budget spent, rounded for the OK badge (0-budget safe). */
function budgetPercentUsed(budget: CostBudgetBlock): number {
  if (budget.monthly_budget_usd <= 0) return 100;
  return Math.min(100, Math.round((budget.month_spend_usd / budget.monthly_budget_usd) * 100));
}

export function CostTotalsCard({ totals, budget }: CostTotalsCardProps) {
  const t = useTranslations("analytics.costs");
  const tb = useTranslations("analytics.budget");
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
        <div className="flex items-center gap-2">
          {budget && (
            <Badge
              variant="outline"
              data-testid="costs-budget-badge"
              title={`${usd(budget.month_spend_usd)} / ${usd(budget.monthly_budget_usd)}`}
              className={
                budget.over_budget
                  ? budget.budget_mode === "block"
                    ? "rounded-full border-destructive/40 bg-destructive/10 text-destructive"
                    : "rounded-full border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400"
                  : "rounded-full border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
              }
            >
              {budget.over_budget
                ? budget.budget_mode === "block"
                  ? tb("badgeBlocked")
                  : tb("badgeOver")
                : tb("badgeOk", { percent: format.number(budgetPercentUsed(budget)) })}
            </Badge>
          )}
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
