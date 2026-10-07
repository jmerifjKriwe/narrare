/**
 * Analytics API client (STATS-002).
 *
 * Typed wrapper around apps/api/narrare/analytics/router.py: monthly AI cost
 * report. Goes through `fetchApi` from ./core (auth-token injection, 401
 * auto-refresh, `/api/v1` prefixing, unified error parsing). Response types
 * mirror the backend Pydantic contracts (narrare/analytics/contracts.py)
 * 1:1 in snake_case — no FE-side re-casing.
 */

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
