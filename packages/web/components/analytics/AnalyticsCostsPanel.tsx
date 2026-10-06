"use client";

/**
 * AnalyticsCostsPanel — monthly AI cost report (STATS-002, ADR-093 §5).
 *
 * Owns month navigation (prev/next, clamped at the current month, aria-live
 * label) and the loading/error/empty states around the report; presentation
 * is split into CostTotalsCard, CostsBreakdownTables and CostTrendChart
 * (RULE-04). Data via `useAnalyticsCosts` (Task 13); strings via
 * `analytics.costs.*` (Task 15 — intent labels fall back to the raw key via
 * `t.has()` until then).
 */

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { StatusMessage } from "@/components/ui/status-message";
import { useAnalyticsCosts } from "@/lib/hooks/useAnalyticsCosts";
import { CostsBreakdownTables } from "./CostsBreakdownTables";
import { CostTotalsCard } from "./CostTotalsCard";
import { CostTrendChart } from "./CostTrendChart";

/** Client-local "YYYY-MM"; zero-padded keys compare lexicographically. */
function currentMonthKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function shiftMonth(month: string, delta: number): string {
  const [year, monthIndex] = month.split("-").map(Number);
  return currentMonthKey(new Date(year, monthIndex - 1 + delta, 1));
}

/** Fetches one month's report and renders its states + sub-components. */
function CostsReport({ month }: { readonly month: string }) {
  const t = useTranslations("analytics.costs");
  const { data, isPending, isError, refetch } = useAnalyticsCosts(month);

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

  return (
    <>
      <CostTotalsCard totals={data.totals} />
      {data.totals.calls === 0 ? (
        <StatusMessage state="empty" message={t("empty")} />
      ) : (
        <>
          <CostsBreakdownTables byIntent={data.by_intent} byModel={data.by_model} />
          <CostTrendChart trend={data.trend} />
        </>
      )}
    </>
  );
}

/** Monthly AI cost report: month nav + totals + breakdowns + six-month trend. */
export function AnalyticsCostsPanel() {
  const t = useTranslations("analytics.costs");
  const [month, setMonth] = useState<string | null>(null);

  // Client-local current month set post-mount (ui-principles §8: no new Date()
  // in initial state → no SSR/client mismatch at month rollover).
  useEffect(() => {
    setMonth(currentMonthKey(new Date()));
  }, []);

  if (month === null) return <StatusMessage state="loading" />;

  const navButton =
    "rounded-md border border-border p-2 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

  return (
    <section className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          aria-label={t("prevMonth")}
          onClick={() => setMonth(shiftMonth(month, -1))}
          className={navButton}
        >
          <ChevronLeft aria-hidden="true" className="h-4 w-4" />
        </button>
        <span
          data-testid="costs-month-label"
          aria-live="polite"
          className="font-mono text-sm font-medium"
        >
          {month}
        </span>
        <button
          type="button"
          aria-label={t("nextMonth")}
          disabled={month >= currentMonthKey(new Date())}
          onClick={() => setMonth(shiftMonth(month, 1))}
          className={`${navButton} disabled:cursor-not-allowed disabled:opacity-50`}
        >
          <ChevronRight aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>
      <CostsReport month={month} />
    </section>
  );
}
