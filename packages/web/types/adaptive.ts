// Adaptive Context REST types — mirror apps/api/narrare/adaptive/schemas.py (RULE-17).
// snake_case matches the Pydantic SSOT (codebase precedent: character-voice-stream.ts).
// Pydantic fields-with-defaults are still required on the wire, so they stay
// required here (only SSE event types use optional `?` fields — see dialogueCoach.ts).

/**
 * Four adaptive weights, each clamped to [0.0, 1.0].
 *
 * RULE-17 contract parity: mirrors `AdaptiveWeightsResponse` (frozen, read-only).
 */
export interface AdaptiveWeightsResponse {
  preference: number;
  voice_fidelity: number;
  style_constraints: number;
  avoidance: number;
}

/**
 * POST body for `/weights` — pre-clamping floats (the service clamps before
 * persistence and returns the clamped value in the response).
 *
 * RULE-17 contract parity: mirrors `AdaptiveWeightsInput` (`extra="forbid"`).
 */
export interface AdaptiveWeightsInput {
  preference: number;
  voice_fidelity: number;
  style_constraints: number;
  avoidance: number;
}

/**
 * POST body for `/toggle`.
 *
 * RULE-17 contract parity: mirrors `AdaptiveToggleInput` (`extra="forbid"`).
 */
export interface AdaptiveToggleInput {
  enabled: boolean;
}

/**
 * Adaptive source data rendered for the dashboard.
 *
 * RULE-17 contract parity: mirrors `AdaptiveSourceSummary` (frozen).
 */
export interface AdaptiveSourceSummary {
  preference_text: string;
  voice_profiles_text: string;
  style_constraints_text: string;
  avoidance_patterns_text: string;
}

/**
 * Response for `GET /adaptive/{project_id}/context`.
 *
 * RULE-17 contract parity: mirrors `AdaptiveContextResponse` (frozen).
 */
export interface AdaptiveContextResponse {
  project_id: string;
  enabled: boolean;
  weights: AdaptiveWeightsResponse;
  sources: AdaptiveSourceSummary;
  has_any_signal: boolean;
}

/**
 * Response for `POST /toggle` and `POST /weights` — the new persisted state.
 *
 * RULE-17 contract parity: mirrors `AdaptiveSettingsResponse` (frozen).
 */
export interface AdaptiveSettingsResponse {
  enabled: boolean;
  weights: AdaptiveWeightsResponse;
}

/**
 * One recent adaptive snapshot for the dashboard history list (Phase 5 Task 7).
 *
 * FORWARD DECLARATION — NOT yet RULE-17-verified: backend endpoint A
 * (`GET /adaptive/{project_id}/snapshots`) is not yet shipped, so there is no
 * Pydantic schema to mirror. When that endpoint lands, reconcile this against
 * its response model field-by-field (same as the types above).
 */
export interface AdaptiveSnapshot {
  invocation_id: string;
  created_at: string;
  adaptive_source_summary: Record<string, string> | null;
  adaptive_weights: Record<string, number> | null;
}
