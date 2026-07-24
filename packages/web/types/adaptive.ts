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
 * One row in the Recent Adaptive Activity timeline (ADR-070).
 *
 * RULE-17 contract parity: mirrors `AdaptiveSnapshotItem` (frozen). Reconciled
 * against apps/api/narrare/adaptive/schemas.py when endpoint A shipped —
 * field names, types, and optionality match exactly (`str | None` → `| null`
 * because Pydantic serialises defaulted fields as `null`, never omitted).
 */
export interface AdaptiveSnapshotItem {
  invocation_id: string | null;
  novel_id: string | null;
  intent: string;
  mode: string | null;
  created_at: string;
  source_summary: Record<string, string> | null;
  weights: AdaptiveWeightsResponse | null;
}

/**
 * Response envelope for `GET /adaptive/{project_id}/snapshots` (ADR-070).
 *
 * RULE-17 contract parity: mirrors `AdaptiveSnapshotsResponse` (frozen). The
 * endpoint returns this wrapper, NOT a bare array — the component reads `.items`.
 */
export interface AdaptiveSnapshotsResponse {
  project_id: string;
  items: AdaptiveSnapshotItem[];
}
