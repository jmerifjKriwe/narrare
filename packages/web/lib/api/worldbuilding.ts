/**
 * Worldbuilding analysis API — types and client functions.
 *
 * Types mirror the Pydantic schemas in worldbuilding_contracts.py (RULE-17).
 * Components never call fetch directly — use TanStack Query hooks from
 * lib/hooks/useWorldbuilding.ts.
 */

import { fetchApi } from "./client";

// --- Enums ---

export type WorldbuildingSeverity = "critical" | "major" | "minor" | "info";

export type GapType =
  | "missing_entity"
  | "missing_field"
  | "missing_connection"
  | "missing_body"
  | "undefined_type";

export type ConsistencyCategory =
  | "geography"
  | "politics"
  | "economics"
  | "system_rules"
  | "timeline"
  | "character"
  | "entry_internal"
  | "relationship_asymmetry";

// --- Finding Types ---

export interface GapFinding {
  entity_id: string | null;
  entity_name: string | null;
  entity_type: string | null;
  gap_type: GapType;
  field_key: string | null;
  description: string;
  related_entity_type: string | null;
  story_relevance: number;
  severity: WorldbuildingSeverity;
}

export interface ConnectionSuggestion {
  finding_index: number;
  source_entity_id: string;
  source_entity_name: string;
  source_entity_type: string;
  target_entity_id: string;
  target_entity_name: string;
  target_entity_type: string;
  suggested_rel_type: string;
  inverse_rel_type: string | null;
  reasoning: string;
  confidence: number;
  story_relevance: number;
}

export interface ConsistencyIssue {
  finding_index: number;
  category: ConsistencyCategory;
  entity_ids: string[];
  entity_names: string[];
  description: string;
  contradiction: string;
  suggested_resolution: string | null;
  severity: WorldbuildingSeverity;
  confidence: number;
}

// --- Request / Response ---

export interface WorldbuildingAnalysisRequest {
  entity_types?: string[] | null;
  include_gaps?: boolean;
  include_connections?: boolean;
  include_consistency?: boolean;
  max_findings?: number;
  refresh?: boolean;
}

export interface WorldbuildingAnalysisResponse {
  novel_id: string;
  entity_count: number;
  gap_findings: GapFinding[];
  connection_suggestions: ConnectionSuggestion[];
  consistency_issues: ConsistencyIssue[];
  worldbuilding_score: number;
  overall_assessment: string;
  summary: Record<string, number>;
  analyzed_at: string;
}

export interface WorldbuildingApplyResponse {
  success: boolean;
  created_count: number;
  failed_count: number;
  errors: string[];
}

/**
 * Router-level request body for applying connections.
 *
 * Combines the finding indices with the full analysis response
 * so the service can look up entity IDs and relationship types.
 * Matches router_worldbuilding.py::WorldbuildingApplyRequestBody exactly.
 */
export interface WorldbuildingApplyRequestBody {
  finding_indices: number[];
  analysis: WorldbuildingAnalysisResponse;
}

// --- API functions ---

export const worldbuildingApi = {
  /**
   * Run a worldbuilding analysis for a project.
   *
   * POST /novels/{novelId}/kb/worldbuilding/analyze
   * Returns gap findings, connection suggestions, and consistency issues.
   */
  analyze: (novelId: string, request?: WorldbuildingAnalysisRequest, signal?: AbortSignal) =>
    fetchApi<WorldbuildingAnalysisResponse>(`/novels/${novelId}/kb/worldbuilding/analyze`, {
      method: "POST",
      body: JSON.stringify(request ?? {}),
      signal,
    }),

  /**
   * Apply selected connection suggestions as KB relationships.
   *
   * POST /novels/{novelId}/kb/worldbuilding/apply
   * Requires the original analysis response for context.
   */
  applyConnections: (novelId: string, body: WorldbuildingApplyRequestBody, signal?: AbortSignal) =>
    fetchApi<WorldbuildingApplyResponse>(`/novels/${novelId}/kb/worldbuilding/apply`, {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    }),
};
