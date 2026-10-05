/**
 * KB entity-resolution API client (ADR-085, F3 plan Task 5) — the minimal
 * suggestions-review surface the corpus-pass dedup gate needs (spec §8):
 * list suggestions, endorse (executes the merge), reject (persists the
 * dismissal), plus one user-initiated re-analysis.
 *
 * REST-only JSON endpoints over `fetchApiRaw` (scoped here, same as
 * `bulkExtraction.ts`) — non-OK responses reject with
 * {@link ResolutionApiError} carrying the HTTP status: a 409 endorse is the
 * EXPECTED stale/concurrent-resolve outcome and drives distinct UI copy.
 *
 * Types are the RULE-17 EXACT mirror of
 * `apps/api/narrare/kb/entity_resolution/schemas_resolution.py` —
 * field-for-field (pinned by compile-time tables + runtime key sets in
 * `kbResolution.test.ts`), with verbatim backend names for traceability.
 *
 * Semantics the UI must respect (ADR-085 analysis_service):
 * - GET suggestions serves the analysis CACHE validated against the current
 *   entries hash — a miss (never analyzed, invalidated, stale after a KB
 *   mutation) yields the EMPTY response, never a recompute and never a 404.
 * - endorse INVALIDATES the server cache; a subsequent GET returns empty.
 *   Clients must therefore NOT refetch the list after an action — optimistic
 *   removal stands in, and `analyzeSuggestions` (refresh: true) is the
 *   authoritative refresh.
 * - reject does NOT touch the cache; the dismissal ledger filters it from
 *   every served analysis retroactively.
 *
 * @module kbResolution
 */

import { fetchApiRaw } from "./client";

// --- Types (RULE-17 mirror of entity_resolution/schemas_resolution.py) ---

/** Bands that may appear in the suggestion list (SUPPRESSED never surfaces). */
export type SuggestionBand = "REVIEW" | "AUTO_ELIGIBLE";

/** Per-signal evidence attached to one suggestion (evidence transparency). */
export interface SignalEvidence {
  /** Signal id, e.g. "name_tier" or "temporal". */
  signal: string;
  /** Normalized signal value in [-1, 1] (+ corroborate, − contradict). */
  value: number;
  /** Whether this signal vetoed the pair (caps confidence, blocks AUTO). */
  veto: boolean;
  /** Human-readable evidence string surfaced in the UI. */
  detail: string;
}

/** One surfaced merge suggestion (band REVIEW or AUTO_ELIGIBLE). */
export interface SuggestionResponse {
  /** Stateless identity: sha256(min(idA,idB) ‖ max(idA,idB))[:16]. */
  suggestion_id: string;
  /** First entry id (min by UUID ordering). */
  entry_a_id: string;
  /** Second entry id (max by UUID ordering). */
  entry_b_id: string;
  /** KB name of entry_a_id at analysis time. */
  name_a: string;
  /** KB name of entry_b_id at analysis time. */
  name_b: string;
  /** Calibrated pair confidence in [0, 1] (spec §4 formula). */
  confidence: number;
  /** Resolution band; AUTO_ELIGIBLE never auto-executes in v1. */
  band: SuggestionBand;
  /** True iff band == AUTO_ELIGIBLE — benchmark/policy input only. */
  auto_merge_eligible: boolean;
  /** All five signal results in canonical S1..S5 order. */
  signals: SignalEvidence[];
  /** LLM adjudicator note for REVIEW pairs; null when unannotated. */
  adjudication_note: string | null;
}

/** Per-band pair counts for one analysis run. */
export interface BandStats {
  /** Pairs in the REVIEW band (surfaced). */
  review: number;
  /** Pairs in the AUTO_ELIGIBLE band (surfaced, flagged). */
  auto_eligible: number;
  /** Pairs below the REVIEW threshold (never surfaced). */
  suppressed: number;
}

/** Detection result for one novel scope (analyze + GET suggestions shape). */
export interface ResolutionAnalysisResponse {
  /** Surfaced suggestions (REVIEW or AUTO_ELIGIBLE bands only). */
  suggestions: SuggestionResponse[];
  /** Per-band counts including suppressed pairs. */
  stats: BandStats;
  /** Whether this response came from the analysis cache. */
  cache_hit: boolean;
}

/** One scalar metadata conflict resolved in the survivor's favor (§6.2). */
export interface MergeConflict {
  /** Dotted metadata path of the conflict, e.g. "gender". */
  key: string;
  /** Value kept (the survivor's). */
  survivor_value: unknown;
  /** Value overridden (the loser's) — preserved, not lost. */
  loser_value: unknown;
}

/** Outcome of one executed merge (spec §6) — the endorse response. */
export interface MergeExecutionResult {
  /** Entry that absorbed the loser. */
  survivor_id: string;
  /** Entry deprecated by the merge (never deleted, §6.4). */
  loser_id: string;
  /** Top-level loser metadata keys incorporated without conflict. */
  merged_fact_keys: string[];
  /** Edges re-pointed from the loser to the survivor (§6.3). */
  repointed_relationships: number;
  /** Edges left untouched (constraint collisions, self-references). */
  skipped_relationships: number;
  /** Scalar conflicts resolved in the survivor's favor (§6.2). */
  conflicts: MergeConflict[];
}

// --- Status-carrying error + response parsing ---

/** Error from a resolution endpoint carrying the HTTP status (409 stale). */
export class ResolutionApiError extends Error {
  /** HTTP status code (409 stale/conflict / 422 validation / …). */
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ResolutionApiError";
    this.status = status;
  }
}

/**
 * Parse a `fetchApiRaw` response: JSON body on success, typed error with the
 * status otherwise. The detail extraction mirrors `fetchApi`'s error shape
 * (string detail, or FastAPI validation arrays joined from `msg` fields).
 */
async function parseResolutionResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const detail = body?.detail;
  const message =
    typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail
            .map((entry) => (typeof entry?.msg === "string" ? entry.msg : String(entry)))
            .join("; ")
        : `HTTP ${response.status}`;
  throw new ResolutionApiError(response.status, message);
}

/** TanStack Query cache key for one novel's served analysis. */
export const resolutionSuggestionsQueryKey = (novelId: string) =>
  ["kb-resolution-suggestions", novelId] as const;

// --- API functions ---

export const kbResolutionApi = {
  /**
   * Serve the CACHED analysis without recomputing (empty when never
   * analyzed or stale after a KB mutation — 404-free, spec §7).
   */
  listSuggestions: (novelId: string, signal?: AbortSignal) =>
    fetchApiRaw(`/novels/${novelId}/kb/resolution/suggestions`, { signal }).then(
      parseResolutionResponse<ResolutionAnalysisResponse>,
    ),

  /**
   * On-demand re-analysis (user-initiated — refresh: true skips the cache
   * read and forces a detection recompute on the CURRENT entries). Unlike
   * the completion-time auto-trigger this route is the adjudicated analyzer
   * (LLM annotation for REVIEW pairs, server-side rate limiter).
   */
  analyzeSuggestions: (novelId: string, signal?: AbortSignal) =>
    fetchApiRaw(`/novels/${novelId}/kb/resolution/analyze`, {
      method: "POST",
      body: JSON.stringify({ refresh: true }),
      signal,
    }).then(parseResolutionResponse<ResolutionAnalysisResponse>),

  /**
   * Re-validate + execute the merge for one suggestion (spec §6/§7); 409
   * when stale, rejected, or low-band. No body — the §6.1 deterministic
   * total order picks the survivor.
   */
  endorseSuggestion: (novelId: string, suggestionId: string, signal?: AbortSignal) =>
    fetchApiRaw(`/novels/${novelId}/kb/resolution/suggestions/${suggestionId}/endorse`, {
      method: "POST",
      signal,
    }).then(parseResolutionResponse<MergeExecutionResult>),

  /** Persist the dismissal (204) — retroactively filtered from every serve. */
  rejectSuggestion: (novelId: string, suggestionId: string, signal?: AbortSignal) =>
    fetchApiRaw(`/novels/${novelId}/kb/resolution/suggestions/${suggestionId}/reject`, {
      method: "POST",
      signal,
    }).then(parseResolutionResponse<undefined>),
};
