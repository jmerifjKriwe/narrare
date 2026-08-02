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

/**
 * Machine-stable reason code for one Policy-alpha join treatment.
 *
 * Mirrors the backend ``JoinReasonCode`` Literal
 * (narrare_core.series.schemas). The frontend resolves each code via i18n
 * (``series.join.reason.<code>``); the English ``reason`` tooltip on the same
 * schema is the human fallback for non-i18n clients (MCP/CLI). These are
 * STABLE WIRE VALUES — do NOT rename without a coordinated i18n migration, or
 * the frontend translation breaks silently (the exact C3 failure this union
 * exists to prevent).
 */
export type JoinReasonCode =
  | "entity_default_canon"
  | "entity_default_overlay"
  | "canon_nonempty_overlay";

/** Per-entry decision in a JoinPreview (JoinEntryTreatment). */
export interface JoinEntryTreatment {
  entry_id: string;
  slug: string;
  entity_type: string;
  current_scope: "novel";
  target_scope: KBScope;
  /**
   * Machine-stable code the frontend resolves via i18n
   * (``series.join.reason.<code>``). C3 fix.
   */
  reason_code: JoinReasonCode;
  /** Human-readable English tooltip (MCP/CLI fallback, RULE-12 four-client). */
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

// --- Scope-discriminated KB entries (Slice 5) ---
//
// Mirror narrare_core.kb.schemas.entry (SeriesKBEntry / NovelKBEntry). The
// physical ``kb_entries`` scope invariant (Alembic 0037 CHECK constraint) is
// reflected at the type level: a Series-Canon entry carries ``series_id`` and
// null ``novel_id``/``base_entry_id``; a Novel-Overlay entry carries
// ``novel_id``. ``scope`` is the virtual discriminator (no physical column).
//
// NOTE: the response field is ``metadata_`` (trailing underscore) — Pydantic
// serializes the Core attribute name as-is. This differs from the create/update
// request bodies, which use ``metadata`` (no underscore).

/** Common fields shared by both KB entry scopes. */
interface ScopedKBEntryBase {
  id: string;
  entity_type: string;
  name: string;
  slug: string;
  status: string;
  body: string | null;
  metadata_: Record<string, unknown> | null;
  tags: string[] | null;
  template_version: string | null;
  source: string;
  review_status: string;
  embeddings_dirty: boolean;
  last_referenced_at: string | null;
  usage_count: number;
  created_at: string | null;
  updated_at: string | null;
}

/** Series-Canon KB entry — shared across all novels (scope="series"). */
export interface SeriesKBEntry extends ScopedKBEntryBase {
  scope: "series";
  series_id: string;
  novel_id: null;
  base_entry_id: null;
}

/** Novel-Overlay KB entry — valid in one specific novel (scope="novel"). */
export interface NovelKBEntry extends ScopedKBEntryBase {
  scope: "novel";
  novel_id: string;
  series_id: string | null;
  base_entry_id: string | null;
}

/** Union of the two scope-discriminated KB entry shapes. */
export type ScopedKBEntry = SeriesKBEntry | NovelKBEntry;

/**
 * POST /api/v1/series/{id}/kb body (KBEntryCreate).
 *
 * Request uses ``metadata`` (no underscore); the response serializes ``metadata_``.
 */
export interface CanonEntryCreate {
  entity_type: string;
  name: string;
  slug?: string | null;
  status?: string;
  tags?: string[] | null;
  metadata?: Record<string, unknown> | null;
  body?: string | null;
  template_version?: string | null;
  source?: string;
  review_status?: string;
}

/** PATCH /api/v1/series/{id}/kb/{entryId} body (KBEntryUpdate) — all optional. */
export interface CanonEntryUpdate {
  name?: string | null;
  slug?: string | null;
  entity_type?: string;
  status?: string;
  tags?: string[] | null;
  metadata?: Record<string, unknown> | null;
  body?: string | null;
  template_version?: string | null;
}
