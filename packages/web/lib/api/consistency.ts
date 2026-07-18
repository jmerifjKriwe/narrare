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
  /**
   * Number of issues hidden because they matched a past dismissal in mem0
   * (CR-AUFG-03-10 semantic suppression layer). ``0`` when mem0 is disabled,
   * unavailable, or found no matches. Doubles as an audit signal so the UI
   * can show "N known false positives hidden".
   */
  suppressed_count: number;
  checked_at: string;
}

// --- Dismissed findings (CR-AUFG-07-26) ---

export interface DismissFindingRequest {
  fingerprint: string;
  reason?: string;
}

export interface DismissedFindingsResponse {
  fingerprints: string[];
}

/**
 * Stable fingerprint for a consistency finding (CR-AUFG-07-26).
 *
 * Matches the backend contract ``description::entity_names.join(",")``.
 * Entity names are sorted so the key is order-independent — the LLM may emit
 * entities in a different order across re-runs, but the same finding must
 * map to the same dismissed fingerprint.
 *
 * Does not mutate the source ``entity_names`` array.
 */
export function consistencyFingerprint(issue: ConsistencyIssue): string {
  return `${issue.description}::${[...issue.entity_names].sort().join(",")}`;
}

// --- API functions ---

export const consistencyApi = {
  /**
   * Run a consistency check on the project's KB.
   *
   * POST /novels/{novelId}/kb/consistency-check
   * Combines entry-internal, relationship asymmetry, and cross-entity analysis.
   */
  checkConsistency: (novelId: string, request?: ConsistencyCheckRequest, signal?: AbortSignal) =>
    fetchApi<ConsistencyCheckResponse>(`/novels/${novelId}/kb/consistency-check`, {
      method: "POST",
      body: JSON.stringify(request ?? {}),
      signal,
    }),

  /**
   * Dismiss (ignore) a consistency finding so it is hidden on future checks.
   *
   * POST /novels/{novelId}/kb/consistency/dismiss
   */
  dismissFinding: (novelId: string, request: DismissFindingRequest) =>
    fetchApi<{ success: boolean }>(`/novels/${novelId}/kb/consistency/dismiss`, {
      method: "POST",
      body: JSON.stringify(request),
    }),

  /**
   * List all dismissed finding fingerprints for a novel.
   *
   * GET /novels/{novelId}/kb/consistency/dismissed
   */
  listDismissed: (novelId: string) =>
    fetchApi<DismissedFindingsResponse>(`/novels/${novelId}/kb/consistency/dismissed`),

  /**
   * Un-dismiss a previously dismissed finding.
   *
   * DELETE /novels/{novelId}/kb/consistency/dismissed/{fingerprint}
   * The fingerprint is URL-encoded because it contains "::" and ",".
   */
  undismissFinding: (novelId: string, fingerprint: string) =>
    fetchApi<{ success: boolean }>(
      `/novels/${novelId}/kb/consistency/dismissed/${encodeURIComponent(fingerprint)}`,
      {
        method: "DELETE",
      },
    ),
};
