/**
 * Analytics API client (STATS-002).
 *
 * Typed wrapper around apps/api/narrare/analytics/router.py: monthly AI cost
 * report. Goes through `fetchApi` from ./core (auth-token injection, 401
 * auto-refresh, `/api/v1` prefixing, unified error parsing). Response types
 * mirror the backend Pydantic contracts (narrare/analytics/contracts.py)
 * 1:1 in snake_case — no FE-side re-casing.
 */

import type { BudgetMode } from "@/types";
import { fetchApi, fetchApiRaw } from "./core";

/** Aggregate over all usage recorded in the requested month. */
export interface CostTotals {
  calls: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  /** Calls whose cost was NULL at write time. */
  unpriced_calls: number;
}

/**
 * Budget overlay on the costs report (STATS-002 budgets, ADR-094 spec A-6).
 * Numbers are floats (backend contract converts the settings Decimal);
 * `over_budget` uses the same `>=` boundary as the block-mode gate.
 */
export interface CostBudgetBlock {
  monthly_budget_usd: number;
  budget_mode: BudgetMode;
  month_spend_usd: number;
  over_budget: boolean;
}

/** Per-intent breakdown row (sorted by cost, descending). */
export interface CostIntentRow {
  intent: string;
  calls: number;
  cost_usd: number;
  unpriced_calls: number;
}

/** Per-(provider, model) breakdown row (sorted by cost, descending). */
export interface CostModelRow {
  provider: string;
  model_id: string;
  calls: number;
  cost_usd: number;
  unpriced_calls: number;
}

/** One month of the six-month trend (`month` is `YYYY-MM`). */
export interface CostTrendPoint {
  month: string;
  cost_usd: number;
}

/**
 * Monthly AI cost overview: month breakdowns + six-month trend.
 *
 * `totals`/`by_intent`/`by_model` are scoped to `month`; `trend` spans the
 * six months ending with `month` (oldest first, zero months included).
 */
export interface CostMonthReport {
  month: string;
  totals: CostTotals;
  by_intent: CostIntentRow[];
  by_model: CostModelRow[];
  trend: CostTrendPoint[];
  /** Budget overlay — null when the user set no budget (badge hidden). */
  budget: CostBudgetBlock | null;
}

/** One UTC day of the writing window (`date` is `YYYY-MM-DD`, deletes negative). */
export interface DailyPoint {
  date: string;
  words: number;
}

/** Consecutive-active-day streaks (today-grace rule, spec E-4). */
export interface Streaks {
  current: number;
  longest: number;
}

/** Novel goal overlay — target vs LIVE manuscript words (spec E-4). */
export interface GoalBlock {
  target_words: number;
  current_words: number;
  /** One decimal place. */
  progress_pct: number;
}

/**
 * Writing-activity report (STATS-001 spec E-5): `dailies` spans the last
 * 90 days ending today (UTC days, zero-filled, oldest first); `total_words`
 * is the all-time net words for the scope (not window-capped). `goal` is
 * present only for a novel-scoped request whose novel has a target set —
 * the backend serializes `null` otherwise.
 */
export interface WritingReport {
  dailies: DailyPoint[];
  streaks: Streaks;
  today_words: number;
  total_words: number;
  goal: GoalBlock | null;
}

/**
 * Parse the suggested filename from a Content-Disposition header. Mirrors
 * lib/api/export.ts (same backend header shape); falls back to the canonical
 * `narrare-costs-<month>.csv` name built by the export endpoint.
 */
function parseCsvFilename(disposition: string | null, month: string): string {
  if (!disposition) return `narrare-costs-${month}.csv`;
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  return match?.[1] ?? `narrare-costs-${month}.csv`;
}

export const analyticsApi = {
  /** GET /analytics/costs?month=YYYY-MM — month report + six-month trend. */
  costs: (month: string) =>
    fetchApi<CostMonthReport>(`/analytics/costs?month=${encodeURIComponent(month)}`),

  /**
   * GET /analytics/writing[?novel_id=<uuid>] — dailies/streaks/totals; the
   * goal block appears only for a novel-scoped request. No novel selected →
   * the request URL carries no query param at all.
   */
  writing: (novelId?: string | null) => {
    const query = novelId ? `?novel_id=${encodeURIComponent(novelId)}` : "";
    return fetchApi<WritingReport>(`/analytics/writing${query}`);
  },

  /**
   * GET /analytics/costs/export?month=YYYY-MM — fetch the month's CSV as a
   * Blob and trigger a browser download (object-URL `<a download>` click →
   * revoke; same DOM pattern as useExportPanel's triggerDownload, inlined
   * here because the binding contract makes this helper the whole download).
   *
   * Uses fetchApiRaw (lib/api/core.ts already exposes the native Response —
   * no wrapper extension needed) for the blob read + auth + 401 refresh.
   */
  async downloadCostsCsv(month: string): Promise<void> {
    const response = await fetchApiRaw(
      `/analytics/costs/export?month=${encodeURIComponent(month)}`,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = parseCsvFilename(response.headers.get("Content-Disposition"), month);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  },
};
