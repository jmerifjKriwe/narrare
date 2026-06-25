/**
 * Character Arc API — types and client for the character arc analysis endpoint.
 *
 * Types mirror the Pydantic schemas in apps/api/narrare/planning/schemas.py
 * (RULE-17). All field names use snake_case to match the backend exactly.
 * Components never call fetch directly — use this function via the
 * `useAIOperation` hook (ADR-043).
 *
 * @module character-arc
 */

import { fetchApi } from "./client";

// ---------------------------------------------------------------------------
// Types (mirror apps/api/narrare/planning/schemas.py)
// ---------------------------------------------------------------------------

/** Request body for character arc generation. */
export interface CharacterArcRequest {
  character_name: string;
  character_current_state: string;
  character_goal_state: string;
}

/** Known arc types. The backend returns a free-form string, so unknown values
 *  are handled gracefully by the UI (falls back to a neutral badge). */
export type ArcType = "growth" | "fall" | "transformation" | "flat";

/** A single phase in a character arc. */
export interface ArcPhaseResponse {
  phase_name: string;
  description: string;
  emotional_state: string;
  turning_point: string;
  chapters_suggested: string;
}

/** Response with full character arc analysis. */
export interface CharacterArcResponse {
  character_name: string;
  starting_state: string;
  ending_state: string;
  arc_type: string;
  phases: ArcPhaseResponse[];
  key_relationships: string[];
  internal_conflict: string;
  resolution: string;
}

// ---------------------------------------------------------------------------
// API function
// ---------------------------------------------------------------------------

/**
 * Generate a character development arc.
 *
 * POST /planning/character-arc/{novelId}
 *
 * @param novelId    The novel UUID.
 * @param request    Character name + optional current/goal state.
 * @param signal     Optional AbortSignal for cancellation.
 */
export function generateCharacterArc(
  novelId: string,
  request: CharacterArcRequest,
  signal?: AbortSignal,
): Promise<CharacterArcResponse> {
  return fetchApi<CharacterArcResponse>(`/planning/character-arc/${novelId}`, {
    method: "POST",
    body: JSON.stringify(request),
    signal,
  });
}
