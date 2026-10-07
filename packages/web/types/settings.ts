// User & project settings, AI provider config, token limits

export interface UserSettings {
  user_id: string;
  display_name: string;
  ui_language: string;
  theme: "light" | "dark" | "system";
  updated_at: string;
}

export interface ProjectSettings {
  novel_id: string;
  autosave_interval: number;
  default_language: string;
  ai_provider: string;
  ai_model: string;
  model_overrides: string;
  /**
   * Spec 3: per-novel opt-out flag for the series-voice Delta model (ADR-078).
   * Read from the ORM column added in migration 0039 (defaults ``true``). When
   * ``false`` the novel falls back to its own ``author_voice`` only and the
   * series voice is skipped at generation-assembly time.
   */
  use_series_voice: boolean;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// AI Provider & Settings types
// ---------------------------------------------------------------------------

export interface UserProvider {
  id: string;
  provider_name: string;
  has_api_key: boolean;
  api_key_last4: string;
  base_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateProviderRequest {
  provider_name: string;
  api_key: string;
  base_url?: string | null;
}

export interface UpdateProviderRequest {
  api_key?: string;
  base_url?: string | null;
  is_active?: boolean;
}

export type IntentCategory =
  | "writing"
  | "analysis"
  | "kb"
  | "planning"
  | "extraction"
  | "chat"
  | "research";

/**
 * Public token-limit profile vocabulary (CR-08 P1 D1).
 *
 * `conservative` is intentionally absent: it is a retired legacy alias that
 * the Backend normalizes to `balanced` at the read boundary and never emits.
 * Mirrors `packages/core/narrare_core/llm/token_profiles.py` — parity is
 * enforced by `lib/__tests__/token-profiles.test.ts`.
 */
export type TokenLimitProfile = "quick" | "balanced" | "long_texts" | "comprehensive" | "custom";

export interface ModelOverride {
  provider_id: string;
  model_id: string;
}

/** Tier names for context budget allocation. */
export type ContextTier = "immediate" | "recent" | "kb_referenced" | "kb_suggested" | "pinned";

// ---------------------------------------------------------------------------
// CR-08 P1 — token-limit metadata, calibration, suitability (D1/D4/D5/D6)
// ---------------------------------------------------------------------------

/** One public token-limit profile and its preset output limit (if any). */
export interface TokenProfilePreset {
  readonly value: TokenLimitProfile;
  /** Fixed preset output limit; null for the custom raw mode. */
  readonly preset_output_limit: number | null;
  /** True for the custom raw mode. */
  readonly is_custom: boolean;
}

/** Static token-limit vocabulary and caps, derived from Core by the Backend. */
export interface TokenLimitsCatalog {
  readonly catalogue: readonly TokenProfilePreset[];
  /** Largest raw output limit accepted before provider calibration. */
  readonly absolute_max: number;
  /** Recommended UX slider range; not a provider or API hard maximum. */
  readonly ux_recommended_max: number;
}

/**
 * Evidence status for provider/model output-limit metadata (CR-08 P1 D5).
 * Stale/offline/unknown/invalid must NEVER be displayed as calibrated.
 */
export type CalibrationStatus =
  | "known_fresh"
  | "known_stale"
  | "unknown_model"
  | "offline_no_cache"
  | "invalid_metadata";

/** Typed provider/model calibration evidence for a limit lookup. */
export interface CalibrationMetadata {
  readonly provider: string;
  readonly model_id: string;
  readonly status: CalibrationStatus;
  readonly source: string;
  readonly provider_max_output_tokens: number | null;
  readonly context_window_tokens: number | null;
  readonly source_timestamp: number | null;
  readonly cache_age_seconds: number | null;
  readonly detail: string | null;
}

/** Severity for a single suitability finding (CR-08 P1 D6). */
export type SuitabilitySeverity = "advisory" | "warning" | "hard_block";

/** One suitability finding (advisory / warning / hard_block). */
export interface SuitabilityIssue {
  readonly severity: SuitabilitySeverity;
  readonly code: string;
  readonly message: string;
}

/** Suitability decision for one model/intent/output request. */
export interface SuitabilityMetadata {
  readonly intent: string;
  readonly output_profile: string;
  readonly requested_output_tokens: number;
  readonly effective_output_tokens: number;
  readonly recommended_output_tokens: number;
  readonly minimum_viable_output_tokens: number;
  readonly calibration_status: CalibrationStatus;
  readonly provider_max_output_tokens: number | null;
  readonly severity: SuitabilitySeverity;
  readonly is_allowed: boolean;
  readonly issues: readonly SuitabilityIssue[];
}

/** Resolved token limits from all layers (user → project → env → code). */
export interface TokenLimitsResponse {
  /** Requested raw output limit (before profile/cap resolution). */
  output_limit: number;
  token_profile: TokenLimitProfile;
  /** Effective output limit after applying profile/cap resolution. */
  effective_output_limit: number;
  tier_percentages: Record<ContextTier, number>;
  ws_timeout: number;
  /** Core-derived profile catalogue + caps (CR-08 P1 D1/D4). */
  metadata: TokenLimitsCatalog;
  /** Provider/model calibration evidence, populated when provider/model supplied. */
  calibration: CalibrationMetadata | null;
  /** Suitability decision, populated when provider/model/intent supplied. */
  suitability: SuitabilityMetadata | null;
}

/** Partial update for token limit overrides. */
export interface UpdateTokenLimitsRequest {
  output_limit?: number;
  token_profile?: TokenLimitProfile;
  tier_percentages?: Partial<Record<ContextTier, number>>;
  ws_timeout?: number;
}

/**
 * Budget enforcement mode for the monthly USD budget (STATS-002 budgets,
 * ADR-094): warn = badge only; block = hard stop (429) at the gate.
 */
export type BudgetMode = "warn" | "block";

export interface UserAiSettings {
  user_id: string;
  default_provider_id: string | null;
  default_model: string;
  category_overrides: Record<string, ModelOverride>;
  intent_overrides: Record<string, ModelOverride>;
  /**
   * Monthly spend cap in USD (STATS-002 budgets, ADR-094). Wire format is the
   * backend's Decimal-serialized string (e.g. "25.00"); null = no budget.
   */
  monthly_budget_usd: string | null;
  budget_mode: BudgetMode;
  updated_at: string;
}

export interface UpdateUserAiSettingsRequest {
  default_provider_id?: string | null;
  default_model?: string;
  category_overrides?: Record<string, ModelOverride>;
  intent_overrides?: Record<string, ModelOverride>;
  /**
   * USD amount ≥ 0 with at most two decimals; explicit null unsets the budget
   * (backend distinguishes null from not-provided). Never send budget_mode
   * null — the backend rejects explicit-null mode with 422.
   */
  monthly_budget_usd?: number | null;
  budget_mode?: BudgetMode;
}

export interface ProjectAiSettings {
  novel_id: string;
  category_overrides: Record<string, ModelOverride>;
  intent_overrides: Record<string, ModelOverride>;
  updated_at: string;
}

export interface UpdateProjectAiSettingsRequest {
  category_overrides?: Record<string, ModelOverride>;
  intent_overrides?: Record<string, ModelOverride>;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}
