// Series-history context-preview types (C1 — Context-Window Slider) — mirror
// apps/api/narrare/series/series_history_preview_schemas.py (RULE-17 parity).
// snake_case is preserved to match the Pydantic SSOT.

/** One candidate window size's prediction (mirrors the Core preview). */
export interface SeriesHistoryPreviewEntry {
  window_size: number;
  /** Effective series-history ceiling this prediction was computed against. */
  token_budget: number;
  estimated_tokens: number;
  bands_total: number;
  bands_full: number;
  bands_short: number;
  bands_truncated: number;
  bands_dropped: number;
  bands_missing: number;
  budget_clipped: boolean;
}

/** GET /series/{id}/settings/context-preview response (C1 live preview). */
export interface SeriesHistoryPreviewResponse {
  series_id: string;
  current_window_size: number;
  /** EffectiveContextBudgets verbatim (ADR-082 — effective, not configured). */
  effective_series_history_budget: number;
  effective_context_total: number;
  effective_tier_base: number;
  /** null = model window unknown (uncapped, RULE-11). */
  model_context_window: number | null;
  budget_source: string;
  previews: SeriesHistoryPreviewEntry[];
}
