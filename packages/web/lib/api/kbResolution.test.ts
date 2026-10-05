/**
 * KB entity-resolution API client tests (ADR-085, F3 plan Task 5).
 *
 * Three concerns, mirroring the `bulkExtraction.test.ts` structure:
 * 1. Wire paths + bodies: the four client methods must hit the exact REST
 *    paths of `apps/api/narrare/kb/entity_resolution/router.py`
 *    (`/novels/{id}/kb/resolution/…`) with the exact request bodies
 *    (endorse/reject post NO body; analyze forces `refresh: true` — an
 *    explicit user-initiated re-analysis, never a silent auto-trigger).
 * 2. Status-carrying errors: non-OK responses reject with
 *    `ResolutionApiError` carrying the HTTP status (409 stale endorse is
 *    the EXPECTED concurrent-resolution failure and drives distinct UI copy).
 * 3. RULE-17 mirror parity: every TS type mirrors the field list of its
 *    `entity_resolution/schemas_resolution.py` counterpart EXACTLY —
 *    compile-time field tables (drift fails `pnpm type-check`) plus runtime
 *    key-set assertions (drift fails this suite).
 *
 * @module kbResolution.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/core", () => ({ fetchApiRaw: vi.fn() }));

import { fetchApiRaw } from "@/lib/api/core";
import {
  type BandStats,
  kbResolutionApi,
  type MergeConflict,
  type MergeExecutionResult,
  type ResolutionAnalysisResponse,
  type ResolutionApiError,
  type SignalEvidence,
  type SuggestionBand,
  type SuggestionResponse,
} from "@/lib/api/kbResolution";

const raw = vi.mocked(fetchApiRaw);

/** JSON Response fixture (real Response — the client reads .ok/.status/.json). */
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(body === undefined ? undefined : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => vi.clearAllMocks());

// ---------------------------------------------------------------------------
// RULE-17 mirror fixtures — field lists are the schemas_resolution.py SSOT.
// ---------------------------------------------------------------------------

const SIGNAL_FIELDS: Record<keyof SignalEvidence, true> = {
  signal: true,
  value: true,
  veto: true,
  detail: true,
};

const SUGGESTION_FIELDS: Record<keyof SuggestionResponse, true> = {
  suggestion_id: true,
  entry_a_id: true,
  entry_b_id: true,
  name_a: true,
  name_b: true,
  confidence: true,
  band: true,
  auto_merge_eligible: true,
  signals: true,
  adjudication_note: true,
};

const BAND_STATS_FIELDS: Record<keyof BandStats, true> = {
  review: true,
  auto_eligible: true,
  suppressed: true,
};

const ANALYSIS_FIELDS: Record<keyof ResolutionAnalysisResponse, true> = {
  suggestions: true,
  stats: true,
  cache_hit: true,
};

const MERGE_CONFLICT_FIELDS: Record<keyof MergeConflict, true> = {
  key: true,
  survivor_value: true,
  loser_value: true,
};

const MERGE_RESULT_FIELDS: Record<keyof MergeExecutionResult, true> = {
  survivor_id: true,
  loser_id: true,
  merged_fact_keys: true,
  repointed_relationships: true,
  skipped_relationships: true,
  conflicts: true,
};

// Band literal union — mirror of schemas_resolution.py's `SuggestionBand`.
const BAND_PIN: Record<SuggestionBand, true> = {
  REVIEW: true,
  AUTO_ELIGIBLE: true,
};

const suggestion: SuggestionResponse = {
  suggestion_id: "0f1e2d3c4b5a6978",
  entry_a_id: "10000000-0000-0000-0000-000000000001",
  entry_b_id: "20000000-0000-0000-0000-000000000002",
  name_a: "Elena Varo",
  name_b: "Elena Varo",
  confidence: 0.82,
  band: "REVIEW",
  auto_merge_eligible: false,
  signals: [{ signal: "name_tier", value: 0.8, veto: false, detail: "Tier-1 name match" }],
  adjudication_note: null,
};

const analysis: ResolutionAnalysisResponse = {
  suggestions: [suggestion],
  stats: { review: 1, auto_eligible: 0, suppressed: 3 },
  cache_hit: false,
};

const mergeResult: MergeExecutionResult = {
  survivor_id: "10000000-0000-0000-0000-000000000001",
  loser_id: "20000000-0000-0000-0000-000000000002",
  merged_fact_keys: ["gender"],
  repointed_relationships: 2,
  skipped_relationships: 1,
  conflicts: [{ key: "gender", survivor_value: "female", loser_value: "f" }],
};

describe("kbResolutionApi — wire paths (ADR-085 router)", () => {
  it("listSuggestions GETs …/kb/resolution/suggestions", async () => {
    raw.mockResolvedValueOnce(jsonResponse(analysis));
    await kbResolutionApi.listSuggestions("n1");
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/resolution/suggestions", {
      signal: undefined,
    });
  });

  it("analyzeSuggestions POSTs refresh:true to …/kb/resolution/analyze", async () => {
    raw.mockResolvedValueOnce(jsonResponse(analysis));
    await kbResolutionApi.analyzeSuggestions("n1");
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/resolution/analyze", {
      method: "POST",
      body: JSON.stringify({ refresh: true }),
      signal: undefined,
    });
  });

  it("endorseSuggestion POSTs …/suggestions/{id}/endorse with NO body", async () => {
    raw.mockResolvedValueOnce(jsonResponse(mergeResult));
    await kbResolutionApi.endorseSuggestion("n1", "sug-1");
    // No survivor override — the §6.1 deterministic order picks the survivor.
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/resolution/suggestions/sug-1/endorse", {
      method: "POST",
      signal: undefined,
    });
  });

  it("rejectSuggestion POSTs …/suggestions/{id}/reject (204, no body)", async () => {
    raw.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const result = await kbResolutionApi.rejectSuggestion("n1", "sug-1");
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/resolution/suggestions/sug-1/reject", {
      method: "POST",
      signal: undefined,
    });
    expect(result).toBeUndefined();
  });

  it("forwards the AbortSignal when given", async () => {
    raw.mockResolvedValueOnce(jsonResponse(analysis));
    const controller = new AbortController();
    await kbResolutionApi.listSuggestions("n1", controller.signal);
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/resolution/suggestions", {
      signal: controller.signal,
    });
  });

  it("parses the analysis body and the merge result body", async () => {
    raw.mockResolvedValueOnce(jsonResponse(analysis));
    const listed = await kbResolutionApi.listSuggestions("n1");
    expect(listed.suggestions).toHaveLength(1);
    expect(listed.stats.review).toBe(1);

    raw.mockResolvedValueOnce(jsonResponse(mergeResult));
    const merged = await kbResolutionApi.endorseSuggestion("n1", "sug-1");
    expect(merged.repointed_relationships).toBe(2);
  });
});

describe("kbResolutionApi — status-carrying typed errors", () => {
  it("409 stale endorse → ResolutionApiError with status 409", async () => {
    raw.mockResolvedValueOnce(
      jsonResponse({ detail: "Suggestion is stale or already resolved" }, 409),
    );
    const err = await kbResolutionApi.endorseSuggestion("n1", "sug-1").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(Error);
    expect(err).toMatchObject({ status: 409, message: "Suggestion is stale or already resolved" });
  });

  it("a non-JSON error body degrades to 'HTTP <status>' instead of crashing", async () => {
    raw.mockResolvedValueOnce(new Response("Bad Gateway", { status: 502 }));
    const err = await kbResolutionApi.listSuggestions("n1").catch((e: unknown) => e);
    expect((err as ResolutionApiError).status).toBe(502);
    expect((err as ResolutionApiError).message).toBe("HTTP 502");
  });
});

describe("RULE-17 mirror parity — schemas_resolution.py field lists", () => {
  it("SuggestionResponse mirrors SuggestionResponse exactly", () => {
    expect(Object.keys(suggestion).sort()).toEqual(Object.keys(SUGGESTION_FIELDS).sort());
  });

  it("SignalEvidence mirrors SignalEvidence exactly", () => {
    expect(Object.keys(suggestion.signals[0]).sort()).toEqual(Object.keys(SIGNAL_FIELDS).sort());
  });

  it("BandStats and the analysis response mirror exactly", () => {
    expect(Object.keys(analysis.stats).sort()).toEqual(Object.keys(BAND_STATS_FIELDS).sort());
    expect(Object.keys(analysis).sort()).toEqual(Object.keys(ANALYSIS_FIELDS).sort());
  });

  it("MergeExecutionResult mirrors MergeExecutionResult exactly", () => {
    expect(Object.keys(mergeResult).sort()).toEqual(Object.keys(MERGE_RESULT_FIELDS).sort());
    expect(Object.keys(mergeResult.conflicts[0]).sort()).toEqual(
      Object.keys(MERGE_CONFLICT_FIELDS).sort(),
    );
  });

  it("band union matches the normative set exactly", () => {
    expect(Object.keys(BAND_PIN)).toEqual(["REVIEW", "AUTO_ELIGIBLE"]);
  });
});
