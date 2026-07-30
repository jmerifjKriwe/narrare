// Series types — mirror apps/api/narrare/series/schemas.py (RULE-17 parity).
// snake_case is preserved to match the Pydantic SSOT.

/** Lifecycle of a Series. Mirrors narrare_core.series.schemas.SeriesStatus. */
export type SeriesStatus = "draft" | "active" | "completed";

/**
 * KB scope union. Mirrors the `target_scope` Literal in JoinEntryTreatment and
 * the scope invariant enforced by the KB canon/scope routers. Used by Slice 5
 * (ScopeToggle, useKBScope).
 */
export type KBScope = "series" | "novel";

/** Response for single Series GET/POST/PATCH (SeriesResponse). */
export interface Series {
  id: string;
  user_id: string;
  title: string;
  subtitle: string | null;
  description: string | null;
  genre: string | null;
  writing_language: string | null;
  status: SeriesStatus;
  planned_novel_count: number | null;
  novel_count: number;
}

/** List item: lighter than Series (SeriesSummary). */
export interface SeriesSummary {
  id: string;
  title: string;
  subtitle: string | null;
  status: SeriesStatus;
  novel_count: number;
}

/** POST /api/v1/series body (SeriesCreateRequest). */
export interface SeriesCreate {
  title: string;
  subtitle?: string | null;
  description?: string | null;
  genre?: string | null;
  writing_language?: string | null;
  status?: SeriesStatus;
  planned_novel_count?: number | null;
}

/**
 * PATCH /api/v1/series/{id} body (SeriesUpdateRequest).
 *
 * Mirrors the backend `str | None` per field + `exclude_unset` PATCH semantics
 * in SeriesService._build_patch: `undefined` (omit) = skip, `null` = clear the
 * column, a value = set it. `status` is intentionally non-nullable — it is
 * transitioned, never cleared (a NULL would violate the DB NOT NULL constraint).
 */
export interface SeriesUpdate {
  title?: string | null;
  subtitle?: string | null;
  description?: string | null;
  genre?: string | null;
  writing_language?: string | null;
  status?: SeriesStatus;
  planned_novel_count?: number | null;
}

/** GET/PATCH /api/v1/series/{id}/settings response (SeriesSettingsResponse). */
export interface SeriesSettings {
  series_id: string;
  author_voice: Record<string, unknown> | null;
}

/** PATCH /api/v1/series/{id}/settings body (SeriesSettingsUpdateRequest). */
export interface SeriesSettingsUpdate {
  author_voice?: Record<string, unknown> | null;
}

/** Per-entry decision in a JoinPreview (JoinEntryTreatment). */
export interface JoinEntryTreatment {
  entry_id: string;
  slug: string;
  entity_type: string;
  current_scope: "novel";
  target_scope: KBScope;
  reason: string;
}

/** Result of POST /api/v1/series/{id}/novels — preview step (JoinPreview). */
export interface JoinPreview {
  series_id: string;
  novel_id: string;
  canon_empty: boolean;
  treatments: JoinEntryTreatment[];
}

/** Result of POST /api/v1/series/{id}/novels/{novel_id}/apply (JoinResult). */
export interface JoinResult {
  series_id: string;
  novel_id: string;
  position: number;
  promoted_to_canon: number;
  kept_as_overlay: number;
}
