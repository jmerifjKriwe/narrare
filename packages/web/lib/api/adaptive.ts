/**
 * Adaptive Context REST client (ADR-069 D12 / ADR-070 endpoint A).
 *
 * Thin wrapper over {@link fetchApi} for the four shipped endpoints:
 *  - GET  /adaptive/{project_id}/context   → AdaptiveContextResponse
 *  - POST /adaptive/{project_id}/toggle    (AdaptiveToggleInput)  → AdaptiveSettingsResponse
 *  - POST /adaptive/{project_id}/weights   (AdaptiveWeightsInput) → AdaptiveSettingsResponse
 *  - GET  /adaptive/{project_id}/snapshots → AdaptiveSnapshotsResponse (ADR-070)
 *
 * @module adaptive
 */
import type {
  AdaptiveContextResponse,
  AdaptiveSettingsResponse,
  AdaptiveSnapshotsResponse,
  AdaptiveToggleInput,
  AdaptiveWeightsInput,
} from "@/types";
import { fetchApi } from "./core";

export const adaptiveApi = {
  /** Read the current adaptive state for the dashboard + indicator. */
  getContext: (projectId: string) =>
    fetchApi<AdaptiveContextResponse>(`/adaptive/${projectId}/context`),

  /** Toggle adaptivity on/off; returns the new persisted state. */
  toggle: (projectId: string, enabled: boolean) =>
    fetchApi<AdaptiveSettingsResponse>(`/adaptive/${projectId}/toggle`, {
      method: "POST",
      body: JSON.stringify({ enabled } satisfies AdaptiveToggleInput),
    }),

  /** Update the 4 weights (backend clamps); returns the new persisted state. */
  setWeights: (projectId: string, weights: AdaptiveWeightsInput) =>
    fetchApi<AdaptiveSettingsResponse>(`/adaptive/${projectId}/weights`, {
      method: "POST",
      body: JSON.stringify(weights),
    }),

  /** Recent adaptive activity (ADR-070 endpoint A). Returns the full envelope;
   *  callers read `.items`. Mirrors the backend `AdaptiveSnapshotsResponse`. */
  getSnapshots: (projectId: string, limit = 20) =>
    fetchApi<AdaptiveSnapshotsResponse>(`/adaptive/${projectId}/snapshots?limit=${limit}`),
};
