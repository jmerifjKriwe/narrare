/**
 * KB Consistency Check API — types and client functions.
 *
 * Types mirror the Pydantic schemas in consistency_contracts.py (RULE-17).
 * Reuses ConsistencyIssue, ConsistencyCategory, and WorldbuildingSeverity
 * from worldbuilding.ts — no duplication.
 */

import { fetchApi } from "./client";
import type { ConsistencyIssue } from "./worldbuilding";

// --- Request / Response ---

export interface ConsistencyCheckRequest {
  entity_types?: string[] | null;
  include_entry_internal?: boolean;
  include_asymmetry?: boolean;
  include_cross_entity?: boolean;
  refresh?: boolean;
}

export interface ConsistencyCheckResponse {
  novel_id: string;
  entity_count: number;
  issues: ConsistencyIssue[];
  summary: Record<string, number>;
  checked_at: string;
}

// --- API functions ---

export const consistencyApi = {
  /**
   * Run a consistency check on the project's KB.
   *
   * POST /novels/{novelId}/kb/consistency-check
   * Combines entry-internal, relationship asymmetry, and cross-entity analysis.
   */
  checkConsistency: (novelId: string, request?: ConsistencyCheckRequest) =>
    fetchApi<ConsistencyCheckResponse>(`/novels/${novelId}/kb/consistency-check`, {
      method: "POST",
      body: JSON.stringify(request ?? {}),
    }),
};
