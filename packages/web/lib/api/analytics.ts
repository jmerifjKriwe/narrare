/**
 * Analytics API client (STATS-002).
 *
 * Typed wrapper around apps/api/narrare/analytics/router.py: monthly AI cost
 * report. Goes through `fetchApi` from ./core (auth-token injection, 401
 * auto-refresh, `/api/v1` prefixing, unified error parsing). Response types
 * mirror the backend Pydantic contracts (narrare/analytics/contracts.py)
 * 1:1 in snake_case — no FE-side re-casing.
 */

import { fetchApi } from "./core";

/** Aggregate over all usage recorded in the requested month. */
export interface CostTotals {
  calls: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  /** Calls whose cost was NULL at write time. */
  unpriced_calls: number;
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
}

export const analyticsApi = {
  /** GET /analytics/costs?month=YYYY-MM — month report + six-month trend. */
  costs: (month: string) =>
    fetchApi<CostMonthReport>(`/analytics/costs?month=${encodeURIComponent(month)}`),
};
