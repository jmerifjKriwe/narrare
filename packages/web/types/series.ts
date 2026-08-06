// Series types — mirror apps/api/narrare/series/schemas.py (RULE-17 parity).
// snake_case is preserved to match the Pydantic SSOT.

// The series-scope voice-drift RESPONSE is reused verbatim from the novel-level
// analysis module (AuthorVoiceDriftResponse, RULE-22 — no duplication); only the
// wrapper is named for the series context. The reused sub-types are imported here
// so SeriesVoiceDriftResult is a single self-contained contract mirror.
import type {
  AuthorVoiceDriftNoProfile,
  AuthorVoiceDriftResult,
} from "@/lib/api/author-voice-drift-stream";

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
  /**
   * Spec 2 recency-window: how many preceding bands contribute their full
   * summary to the SeriesHistoryTier context (default 3). Mirrors the API
   * SeriesSettingsResponse field and the ORM/Core default.
   */
  context_window_size: number;
}

// --- Band Summary types (Spec 2 Task 8) --------------------------------------
//
// Mirror apps/api/narrare/series/schemas.py BandSummaryResponse /
// BandSummaryOverrideRequest (RULE-17 parity). snake_case preserved to match
// the Pydantic SSOT.

/**
 * Response for the band-summary GET/POST/PATCH endpoints
 * (BandSummaryResponse).
 *
 * ``override`` takes precedence over the generated ``full_summary`` /
 * ``short_summary`` at SeriesHistoryTier assembly time. ``generated_at`` is the
 * server timestamp of the last (re)generation (ISO-8601 string).
 */
export interface BandSummary {
  novel_id: string;
  full_summary: string | null;
  short_summary: string | null;
  override: string | null;
  generated_at: string;
}

/** PATCH /api/v1/series/{id}/novels/{novelId}/band-summary body. */
export interface BandSummaryOverrideRequest {
  override: string;
}

// --- Series Voice types (Spec 3 Tasks 5–6) -----------------------------------
//
// Mirror apps/api/narrare/series/series_voice_schemas.py
// (SeriesVoiceResponse / SeriesVoiceStateResponse / SeriesVoiceOverrideRequest)
// and narrare_core.profiles.author_voice.AuthorVoiceProfile (RULE-17 parity).
// snake_case is preserved to match the Pydantic SSOT.
//
// The ``SeriesVoiceProfile`` is a structural mirror of the Core
// ``AuthorVoiceProfile``: the UI reads ONLY the descriptive group
// (``voice_analysis`` descriptive fields + ``author_examples``) — the metric
// blocks (``voice_analysis.voice_metrics`` / ``author_metrics``) are
// comparison-only and never rendered (ADR-074 binding, enforced Core-side at
// the consumer). They stay loose-typed here so the wire JSON validates without
// enumerating every nested metric field.

/** Descriptive subset of ``VoiceAnalysis`` (mirrors Core). */
export interface SeriesVoiceAnalysis {
  formality?: number;
  vocabulary_level?: string;
  sentence_profile?: string;
  emotional_range?: string;
  cultural_regional_markers?: string;
  voice_examples?: string[];
  /** Comparison-only metric block (never rendered by the UI). */
  voice_metrics?: Record<string, unknown>;
}

/**
 * Structural mirror of ``AuthorVoiceProfile`` persisted as
 * ``SeriesSettings.author_voice`` (the Delta-model foundation, ADR-078).
 */
export interface SeriesVoiceProfile {
  voice_analysis?: SeriesVoiceAnalysis | null;
  author_examples?: string[] | null;
  /** Comparison-only author prose-level metrics (never rendered by the UI). */
  author_metrics?: Record<string, unknown> | null;
  updated_at?: string | null;
  is_fresh?: boolean;
}

/** GET /api/v1/series/{id}/voice response (SeriesVoiceResponse). */
export interface SeriesVoice {
  series_id: string;
  /** ``null`` = no series voice profiled yet (RULE-11 graceful degradation). */
  author_voice: SeriesVoiceProfile | null;
}

/** POST /api/v1/series/{id}/voice/profile response (SeriesVoiceStateResponse). */
export interface SeriesVoiceState {
  series_id: string;
  novel_id: string;
  author_voice: SeriesVoiceProfile;
}

/**
 * PATCH /api/v1/series/{id}/voice body (SeriesVoiceOverrideRequest).
 *
 * Carried as a raw dict on the wire so the UI can edit the full profile shape;
 * the service validates it as ``AuthorVoiceProfile`` (a malformed override →
 * 422 ``ValidationError``).
 */
export interface SeriesVoiceOverrideRequest {
  author_voice: Record<string, unknown>;
}

/** PATCH /api/v1/series/{id}/settings body (SeriesSettingsUpdateRequest). */
export interface SeriesSettingsUpdate {
  author_voice?: Record<string, unknown> | null;
  /** Bounded to [1, 50] by the backend (SeriesSettingsUpdateRequest). */
  context_window_size?: number | null;
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

// --- Series Cross-Novel Drift types (Spec 4 Task 4) --------------------------
//
// Mirror apps/api/narrare/series/series_consistency_schemas.py
// (SeriesConsistencyCheckResponse) and narrare_core.agents.series_consistency_types
// (CanonConflict) — RULE-17 parity. The check is read-only and stateless in this
// slice: nothing is persisted; every field is a display-only report artifact.
// The voice-drift RESPONSE shape is reused from the novel-level analysis module
// (AuthorVoiceDriftResponse) — only the wrapper is named for the series context
// (RULE-22). snake_case is preserved to match the Pydantic SSOT.

/** Severity of a canon contradiction. Mirrors the CanonConflict.severity Literal. */
export type CanonConflictSeverity = "error" | "warning";

/**
 * A single contradiction between a chapter passage and a Canon entry.
 *
 * RULE-17 contract parity: mirrors ``CanonConflict``
 * (packages/core/narrare_core/agents/series_consistency_types.py).
 */
export interface CanonConflict {
  /** Slug identifying the Canon entry that is contradicted. */
  canon_entry_slug: string;
  /** Human-readable name of the Canon entry. */
  canon_entry_name: string;
  /** Verbatim passage from the chapter text that contradicts Canon. */
  chapter_text_excerpt: string;
  /** What Canon actually says (the contradicted fact). */
  canon_statement: string;
  /** Why the excerpt and the Canon statement cannot both be true. */
  explanation: string;
  /** ``"error"`` = hard contradiction; ``"warning"`` = possible issue. */
  severity: CanonConflictSeverity;
}

/**
 * POST /api/v1/series/{id}/consistency/check response.
 *
 * Mirrors SeriesConsistencyCheckResponse. An **empty** ``conflicts`` list means
 * no contradictions were found — a valid and common result. ``summary`` is the
 * agent's 1-2 sentence overall assessment; the counts are transparency metadata.
 */
export interface SeriesConsistencyResult {
  series_id: string;
  novel_id: string;
  conflicts: CanonConflict[];
  summary: string;
  canon_entry_count: number;
  chapter_count: number;
}

/**
 * POST /api/v1/series/{id}/voice-drift/check response.
 *
 * Reuses the novel-level AuthorVoiceDriftResponse shape verbatim (RULE-22):
 * exactly one of ``result`` / ``no_profile`` is set (author voice is one narrator
 * per novel). Named for the series context because the series endpoint takes the
 * series id in the URL and the novel id in the body; the payload is identical.
 */
export interface SeriesVoiceDriftResult {
  novel_id: string;
  result: AuthorVoiceDriftResult | null;
  no_profile: AuthorVoiceDriftNoProfile | null;
}
