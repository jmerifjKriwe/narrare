// Prompt Override types

export interface PromptInfo {
  prompt_id: string;
  name: string;
  category: string;
  language: string;
  source: string;
  has_override: boolean;
  prompt_version: string;
  is_overridden: boolean;
}

export interface PromptDetail {
  prompt_id: string;
  content: string;
  base_content: string;
  source: string;
  is_overridden: boolean;
  variables: string[];
  metadata: Record<string, unknown>;
}

export interface CascadePath {
  level: string;
  path: string;
  exists: boolean;
}

export interface UpdateInfo {
  prompt_id: string;
  override_version: string;
  current_bundled_version: string;
}

export interface DiffResponse {
  prompt_id: string;
  override_content: string;
  bundled_content: string;
}

// ---------------------------------------------------------------------------
// PROMPT-003 (CR-AUFG-07-16) — preview / reset / live-test types.
//
// These types mirror the Pydantic schemas in
// ``apps/api/narrare/prompts/schemas.py`` 1:1 (RULE-17). Field names use
// snake_case to match the wire format; the backend never camelCases.
// ---------------------------------------------------------------------------

/** ISO language for preview/live-test requests. Mirrors backend ``_PreviewLanguage``. */
export type PromptPreviewLanguage = "en" | "de" | "fr";

/**
 * Variable provenance labels (mirrors
 * ``narrare_core.prompts.variable_taxonomy.VariableProvenance`` enum values).
 */
export type PromptProvenance =
  | "current_author_instruction"
  | "project_writing_profile"
  | "scene_story_plan"
  | "curated_kb"
  | "learned_memory"
  | "generated_suggestion"
  | "system_generated"
  | "feature_dynamic";

/**
 * Variable security classification (mirrors
 * ``narrare_core.prompts.variable_taxonomy.VariableSecurity`` enum values).
 */
export type PromptSecurity =
  | "xml_required"
  | "xml_section_required"
  | "label_required"
  | "generated_label_required"
  | "system_only";

/** Diagnostic kind (mirrors backend ``_DiagnosticKind`` Literal). */
export type PromptDiagnosticKind = "missing_variable" | "unused_variable" | "validation_note";

/**
 * Per-variable UI metadata. Mirrors
 * ``PreviewVariableMetadataResponse`` (Pydantic).
 */
export interface PromptVariableMetadata {
  readonly name: string;
  readonly description: string;
  readonly variable_type: string;
  readonly required: boolean;
  readonly provenance: PromptProvenance;
  readonly security: PromptSecurity;
}

/** Single diagnostic surfaced by the provider-free preview. Mirrors ``PreviewDiagnosticResponse``. */
export interface PromptDiagnostic {
  readonly kind: PromptDiagnosticKind;
  readonly variable_name: string | null;
  readonly message: string;
}

/**
 * Fully-resolved provider-free prompt preview. Mirrors ``PreviewResponse``.
 *
 * The frontend never fabricates this — it always comes from
 * ``POST /api/v1/prompts/{prompt_id}/preview``.
 */
export interface PromptPreview {
  readonly system_prompt: string;
  readonly user_prompt: string;
  readonly first_message: string | null;
  readonly cascade_source: string;
  readonly variables: readonly PromptVariableMetadata[];
  readonly diagnostics: readonly PromptDiagnostic[];
}

/** Request body for ``POST /prompts/{prompt_id}/preview``. Mirrors ``PreviewRequest``. */
export interface PreviewRequest {
  readonly variables: Record<string, string>;
  readonly language: PromptPreviewLanguage;
  readonly genre?: string;
  readonly mode?: string;
  readonly edited_override?: string;
}

/**
 * Reset response with effective-state metadata. Mirrors ``ResetResponse``.
 *
 * Replaces the old boolean-returning ``reset`` API surface for the reset
 * dialog flow; the DELETE endpoint remains for backwards compatibility.
 */
export interface PromptResetResult {
  readonly reset: boolean;
  readonly effective_source: string;
  readonly effective_content: string;
}

/** SSE ``meta`` event payload for the live-test stream. Mirrors ``LiveTestStartedResponse``. */
export interface PromptLiveTestStarted {
  readonly prompt_id: string;
  readonly intent: string;
  readonly model_id: string;
  readonly rate_limit_remaining: number;
}

/** Request body for ``POST /prompts/{prompt_id}/live-test``. Mirrors ``LiveTestRequest``. */
export interface LiveTestRequest {
  readonly variables: Record<string, string>;
  readonly language: PromptPreviewLanguage;
  readonly genre?: string;
  readonly mode?: string;
  readonly edited_override?: string;
  readonly user_prompt: string;
  readonly acknowledge_token_cost: boolean;
}

/**
 * SSE event shape for the live-test stream.
 *
 * The backend emits:
 *   1. ``event: meta``  → ``LiveTestStartedResponse`` payload
 *   2. ``data``         → ``{ text: "..." }`` chunks (no event name)
 *   3. ``event: done``  → ``{ is_final: true }`` (no text)
 *   4. ``data: [DONE]`` → terminal sentinel
 */
export interface PromptLiveTestStreamEvent {
  readonly type?: "meta";
  readonly text?: string;
  readonly error?: string;
  readonly is_final?: boolean;
  readonly prompt_id?: string;
  readonly intent?: string;
  readonly model_id?: string;
  readonly rate_limit_remaining?: number;
}

// ---------------------------------------------------------------------------
// CR-AUFG-07-19 — Prompt History types.
//
// These types mirror the Pydantic schemas in
// ``apps/api/narrare/prompts/schemas_prompt_history.py`` 1:1 (RULE-17). Field
// names use snake_case to match the wire format; the backend never camelCases.
//
// IMPORTANT (RULE-17 reconciliation): ``scope`` is NOT a query parameter on the
// REST endpoints — the backend resolves it deterministically to ``PROJECT``
// (see ``router_prompt_history.py`` ``_DEFAULT_SCOPE``). It still appears in
// the RESPONSE shapes below because the backend echoes it. The TypeScript API
// client therefore does NOT send ``scope``; it is typed here for responses only.
// ---------------------------------------------------------------------------

/** Override scope for a prompt revision. Mirrors backend ``PromptHistoryScope`` StrEnum. */
export type PromptHistoryScope = "project" | "user";

/**
 * Literal token accepted by the compare endpoint for "the current active
 * override". Mirrors ``ACTIVE_TOKEN`` in ``history_mapping.py``.
 */
export const PROMPT_HISTORY_ACTIVE_TOKEN = "active" as const;

/**
 * A single recorded prompt override revision.
 *
 * ``is_active`` is DERIVED server-side (sha256 of the current active override
 * file vs. ``content_hash``); it is never persisted.
 *
 * Mirrors ``PromptRevisionResponse``. The revision's primary key is ``id``
 * (a UUID string), not ``revision_id``.
 */
export interface PromptRevision {
  readonly id: string;
  readonly prompt_id: string;
  readonly scope: PromptHistoryScope;
  readonly content: string;
  readonly content_hash: string;
  readonly actor_id: string | null;
  readonly source: string;
  readonly change_reason: string | null;
  readonly restored_from_id: string | null;
  readonly created_at: string;
  readonly is_active: boolean;
}

/**
 * Paginated list of recorded revisions for a prompt. Mirrors
 * ``PromptHistoryListResponse``. The revision array is ``revisions``
 * (NOT ``items``).
 */
export interface PromptHistoryListResponse {
  readonly prompt_id: string;
  readonly scope: PromptHistoryScope;
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
  readonly revisions: readonly PromptRevision[];
}

/**
 * Side-by-side content for comparing two revisions (or either against the
 * active override). Mirrors ``PromptRevisionCompareResponse``.
 */
export interface PromptRevisionCompareResponse {
  readonly prompt_id: string;
  readonly from_id: string;
  readonly to_id: string;
  readonly from_source: string;
  readonly to_source: string;
  readonly from_content: string;
  readonly to_content: string;
}

/**
 * Result of an append-only restore. Mirrors ``PromptRevisionRestoredResponse``.
 *
 * ``restored_revision`` is the NEW revision recorded for the restore action
 * (``source="restore"``, ``restored_from_id`` → the original revision).
 * ``active_content`` is the content now written to the active override file.
 */
export interface PromptRevisionRestoredResponse {
  readonly prompt_id: string;
  readonly restored_revision: PromptRevision;
  readonly active_content: string;
  readonly previous_active_hash: string | null;
}

/** Result of clearing history (active override file untouched). Mirrors ``PromptHistoryClearedResponse``. */
export interface PromptHistoryClearedResponse {
  readonly prompt_id: string;
  readonly scope: PromptHistoryScope;
  readonly deleted_count: number;
}
