/**
 * Bulk extraction API client tests (F2, ADR-092, plan Task 6).
 *
 * Three concerns:
 * 1. Wire paths + bodies: the five client methods must hit the exact REST
 *    paths of spec §4 (`/novels/{id}/kb/extract/bulk…`) with the exact
 *    request bodies.
 * 2. Status-carrying errors: non-OK responses reject with
 *    `BulkExtractionApiError` carrying the HTTP status (fetchApi flattens
 *    errors to strings — the poll loop needs the status to detect a 404
 *    interrupted job, spec §8.2).
 * 3. RULE-17 mirror parity: every TS type must mirror the field list of its
 *    `apps/api/narrare/kb/bulk_extraction/schemas.py` counterpart EXACTLY.
 *    Enforced twice — exhaustive compile-time field tables (drift fails
 *    `pnpm type-check`) and runtime fixture key-set assertions (drift fails
 *    this suite).
 *
 * @module bulkExtraction.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/core", () => ({ fetchApiRaw: vi.fn() }));

import {
  type BulkChapterState,
  type BulkChapterStatusView,
  type BulkDedupInfo,
  BulkExtractionApiError,
  type BulkExtractionJobView,
  type BulkExtractionResultChapter,
  type BulkExtractionResultsView,
  type BulkExtractionStatusView,
  type BulkExtractionTotals,
  type BulkJobStatus,
  bulkExtractionApi,
  type CapReason,
  type CorpusEstimate,
} from "@/lib/api/bulkExtraction";
import { fetchApiRaw } from "@/lib/api/core";
import type { ExtractionItem, ExtractionOutput } from "@/lib/api/extraction";

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
// RULE-17 mirror fixtures — field lists are the schemas.py SSOT.
// ---------------------------------------------------------------------------

// Compile-time parity tables: a field added to/removed from the TS mirror
// without updating these tables breaks type-check (missing/unknown key).
const TOTALS_FIELDS: Record<keyof BulkExtractionTotals, true> = {
  total: true,
  done: true,
  failed: true,
  remaining: true,
};

const CHAPTER_STATUS_FIELDS: Record<keyof BulkChapterStatusView, true> = {
  chapter_id: true,
  title: true,
  position: true,
  state: true,
  item_count: true,
  error: true,
};

const JOB_VIEW_FIELDS: Record<keyof BulkExtractionJobView, true> = {
  job_id: true,
  novel_id: true,
  status: true,
  created_at: true,
  updated_at: true,
  totals: true,
  error: true,
};

const STATUS_VIEW_FIELDS: Record<keyof BulkExtractionStatusView, true> = {
  ...JOB_VIEW_FIELDS,
  chapters: true,
  dedup: true,
};

const RESULT_CHAPTER_FIELDS: Record<keyof BulkExtractionResultChapter, true> = {
  chapter_id: true,
  title: true,
  position: true,
  state: true,
  output: true,
};

const RESULTS_VIEW_FIELDS: Record<keyof BulkExtractionResultsView, true> = {
  job_id: true,
  novel_id: true,
  status: true,
  chapters: true,
  dedup: true,
};

// F3 corpus pass (plan Task 5): RULE-17 mirror of `BulkDedupInfo`
// (`apps/api/narrare/kb/bulk_extraction/schemas_corpus.py`) — EXACTLY 2
// fields; `suggestion_count` is set iff `analyzed` (server-side invariant).
const BULK_DEDUP_INFO_FIELDS: Record<keyof BulkDedupInfo, true> = {
  analyzed: true,
  suggestion_count: true,
};

// F3 corpus pass (plan Task 4): RULE-17 mirror of `CorpusEstimateView`
// (`apps/api/narrare/kb/bulk_extraction/schemas_corpus.py`) — EXACTLY 8 fields.
const CORPUS_ESTIMATE_FIELDS: Record<keyof CorpusEstimate, true> = {
  total_chapters: true,
  total_word_count: true,
  selected_chapter_ids: true,
  chapter_count: true,
  word_count: true,
  ai_calls: true,
  capped: true,
  cap_reason: true,
};

// `cap_reason` literal union — mirror of `corpus.py`'s `CapReason` alias.
const CAP_REASON_PIN: Record<CapReason, true> = {
  chapters: true,
  words: true,
};

// Normative enum sets (spec §4.1/§4.2) — exhaustive BOTH ways: dropping a
// union member leaves a missing key (type-check error), adding one leaves an
// excess key (also a type-check error). The runtime assertion pins the exact
// key lists against the spec.
const JOB_STATUS_PIN: Record<BulkJobStatus, true> = {
  pending: true,
  running: true,
  cancelling: true,
  completed: true,
  cancelled: true,
  failed: true,
};
const CHAPTER_STATE_PIN: Record<BulkChapterState, true> = {
  pending: true,
  running: true,
  done: true,
  failed: true,
};

const extractionItem: ExtractionItem = {
  item_type: "new_entity",
  entity_type: "character",
  name: "Elena",
  confidence: 0.93,
  source_text: "Elena stepped from the boat.",
  proposed_content: { role: "protagonist" },
  target_entity_id: null,
  conflict_description: null,
  relationship_type: null,
  related_entity_name: null,
};

const output: ExtractionOutput = { results: [extractionItem], analysis_notes: "Strong voice." };

describe("bulkExtractionApi — wire paths (spec §4)", () => {
  it("startBulkExtraction POSTs chapter_ids to …/kb/extract/bulk", async () => {
    raw.mockResolvedValueOnce(jsonResponse({}));
    await bulkExtractionApi.startBulkExtraction("n1", ["c1", "c2"]);
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk", {
      method: "POST",
      body: JSON.stringify({ chapter_ids: ["c1", "c2"] }),
      signal: undefined,
    });
  });

  it("bulkJobStatus GETs …/kb/extract/bulk/{jobId}/status", async () => {
    raw.mockResolvedValueOnce(jsonResponse({}));
    await bulkExtractionApi.bulkJobStatus("n1", "job-9");
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/job-9/status", {
      signal: undefined,
    });
  });

  it("bulkJobResults GETs …/kb/extract/bulk/{jobId}/results", async () => {
    raw.mockResolvedValueOnce(jsonResponse({}));
    await bulkExtractionApi.bulkJobResults("n1", "job-9");
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/job-9/results", {
      signal: undefined,
    });
  });

  it("cancelBulkJob POSTs …/kb/extract/bulk/{jobId}/cancel (no body)", async () => {
    raw.mockResolvedValueOnce(jsonResponse({}));
    await bulkExtractionApi.cancelBulkJob("n1", "job-9");
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/job-9/cancel", {
      method: "POST",
      signal: undefined,
    });
  });

  it("resumeBulkJob POSTs …/kb/extract/bulk/{jobId}/resume (no body)", async () => {
    raw.mockResolvedValueOnce(jsonResponse({}));
    await bulkExtractionApi.resumeBulkJob("n1", "job-9");
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/job-9/resume", {
      method: "POST",
      signal: undefined,
    });
  });

  it("forwards the AbortSignal when given", async () => {
    raw.mockResolvedValueOnce(jsonResponse({}));
    const controller = new AbortController();
    await bulkExtractionApi.bulkJobStatus("n1", "job-9", controller.signal);
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/job-9/status", {
      signal: controller.signal,
    });
  });

  it("parses the JSON body of a successful response", async () => {
    raw.mockResolvedValueOnce(jsonResponse({ job_id: "job-9", novel_id: "n1", status: "pending" }));
    const view = await bulkExtractionApi.startBulkExtraction("n1", ["c1"]);
    expect(view.job_id).toBe("job-9");
  });
});

describe("bulkExtractionApi — status-carrying typed errors", () => {
  it("404 with a detail string → BulkExtractionApiError with status 404", async () => {
    raw.mockResolvedValueOnce(jsonResponse({ detail: "Bulk extraction job not found" }, 404));
    const err = await bulkExtractionApi.bulkJobStatus("n1", "gone").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(BulkExtractionApiError);
    expect(err).toMatchObject({ status: 404, message: "Bulk extraction job not found" });
  });

  it("409 conflict keeps its status so callers can distinguish it from 404", async () => {
    raw.mockResolvedValueOnce(
      jsonResponse({ detail: "A bulk extraction job is already active for this novel" }, 409),
    );
    const err = await bulkExtractionApi.startBulkExtraction("n1", ["c1"]).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(BulkExtractionApiError);
    expect(err).toMatchObject({ status: 409 });
  });

  it("a non-JSON error body degrades to 'HTTP <status>' instead of crashing", async () => {
    raw.mockResolvedValueOnce(new Response("Bad Gateway", { status: 502 }));
    const err = await bulkExtractionApi.bulkJobStatus("n1", "j").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(BulkExtractionApiError);
    expect(err).toMatchObject({ status: 502, message: "HTTP 502" });
  });
});

describe("RULE-17 mirror parity — schemas.py field lists", () => {
  // Runtime fixtures double as the shared poll/response fixtures for the
  // hook tests' expectations about payload shape.
  const totals: BulkExtractionTotals = { total: 42, done: 17, failed: 1, remaining: 24 };
  const jobView: BulkExtractionJobView = {
    job_id: "job-9",
    novel_id: "n1",
    status: "running",
    created_at: "2026-10-03T10:00:00Z",
    updated_at: "2026-10-03T10:01:00Z",
    totals,
    error: null,
  };

  it("BulkExtractionTotals mirrors BulkExtractionTotals exactly", () => {
    expect(Object.keys(totals).sort()).toEqual(Object.keys(TOTALS_FIELDS).sort());
  });

  it("BulkChapterStatusView mirrors BulkChapterStatusView exactly (incl. error)", () => {
    const row = {
      chapter_id: "c1",
      title: "Storm",
      position: 12,
      state: "done" as const,
      item_count: 9,
      error: null,
    };
    // `state: "done"` + `item_count: 9` also mirrors the schemas.py invariant
    // (item_count set iff state done); null error is the non-failed default.
    expect(Object.keys(row).sort()).toEqual(Object.keys(CHAPTER_STATUS_FIELDS).sort());
  });

  it("BulkExtractionJobView mirrors BulkExtractionJobView exactly", () => {
    expect(Object.keys(jobView).sort()).toEqual(Object.keys(JOB_VIEW_FIELDS).sort());
  });

  it("BulkExtractionStatusView = job view + chapters + dedup block", () => {
    const statusView: BulkExtractionStatusView = {
      ...jobView,
      chapters: [
        {
          chapter_id: "c1",
          title: "Storm",
          position: 12,
          state: "done",
          item_count: 9,
          error: null,
        },
        {
          chapter_id: "c2",
          title: "Coda",
          position: 13,
          state: "failed",
          item_count: null,
          error: "agent timeout",
        },
      ],
      dedup: { analyzed: true, suggestion_count: 2 },
    };
    expect(Object.keys(statusView).sort()).toEqual(Object.keys(STATUS_VIEW_FIELDS).sort());
    // Row mirror re-asserted on the failed row: item_count null + error set —
    // the fields the coordinator flagged as MUST-have in the TS mirror.
    expect(Object.keys(statusView.chapters[1]).sort()).toEqual(
      Object.keys(CHAPTER_STATUS_FIELDS).sort(),
    );
  });

  it("BulkDedupInfo mirrors BulkDedupInfo exactly (count iff analyzed)", () => {
    const corpusDone: BulkDedupInfo = { analyzed: true, suggestion_count: 0 };
    const corpusPending: BulkDedupInfo = { analyzed: false, suggestion_count: null };
    expect(Object.keys(corpusDone).sort()).toEqual(Object.keys(BULK_DEDUP_INFO_FIELDS).sort());
    expect(Object.keys(corpusPending).sort()).toEqual(Object.keys(BULK_DEDUP_INFO_FIELDS).sort());
    // The server-side `_count_iff_analyzed` invariant, pinned on the mirror:
    // a count exists ⟺ the analysis ran.
    expect((corpusDone.suggestion_count !== null) === corpusDone.analyzed).toBe(true);
    expect((corpusPending.suggestion_count !== null) === corpusPending.analyzed).toBe(true);
  });

  it("BulkExtractionResultsView mirrors exactly; output present iff done", () => {
    const done: BulkExtractionResultChapter = {
      chapter_id: "c1",
      title: "Storm",
      position: 12,
      state: "done",
      output,
    };
    const failed: BulkExtractionResultChapter = {
      chapter_id: "c2",
      title: "Coda",
      position: 13,
      state: "failed",
      output: null,
    };
    const view: BulkExtractionResultsView = {
      job_id: "job-9",
      novel_id: "n1",
      status: "completed",
      chapters: [done, failed],
      dedup: null,
    };
    expect(Object.keys(view).sort()).toEqual(Object.keys(RESULTS_VIEW_FIELDS).sort());
    expect(Object.keys(done).sort()).toEqual(Object.keys(RESULT_CHAPTER_FIELDS).sort());
    expect(done.output?.results).toHaveLength(1);
    expect(failed.output).toBeNull();
  });

  it("job status + chapter state unions match the normative sets exactly", () => {
    expect(Object.keys(JOB_STATUS_PIN)).toEqual([
      "pending",
      "running",
      "cancelling",
      "completed",
      "cancelled",
      "failed",
    ]);
    expect(Object.keys(CHAPTER_STATE_PIN)).toEqual(["pending", "running", "done", "failed"]);
  });
});

// ---------------------------------------------------------------------------
// F3 corpus pass (plan Task 4) — estimate/start client + CorpusEstimate mirror
// ---------------------------------------------------------------------------

describe("bulkExtractionApi — corpus pass endpoints (F3, plan Task 4)", () => {
  it("corpusEstimate GETs …/kb/extract/bulk/corpus/estimate", async () => {
    raw.mockResolvedValueOnce(jsonResponse({}));
    await bulkExtractionApi.corpusEstimate("n1");
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/corpus/estimate", {
      signal: undefined,
    });
  });

  it("corpusEstimate forwards the AbortSignal when given", async () => {
    raw.mockResolvedValueOnce(jsonResponse({}));
    const controller = new AbortController();
    await bulkExtractionApi.corpusEstimate("n1", controller.signal);
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/corpus/estimate", {
      signal: controller.signal,
    });
  });

  it("startCorpusPass POSTs …/kb/extract/bulk/corpus with NO body", async () => {
    raw.mockResolvedValueOnce(jsonResponse({}));
    await bulkExtractionApi.startCorpusPass("n1");
    expect(raw).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/corpus", {
      method: "POST",
      signal: undefined,
    });
  });

  it("startCorpusPass parses the returned job view (201)", async () => {
    raw.mockResolvedValueOnce(
      jsonResponse(
        {
          job_id: "job-corpus",
          novel_id: "n1",
          status: "pending",
          created_at: "2026-10-03T12:00:00Z",
          updated_at: "2026-10-03T12:00:00Z",
          totals: { total: 0, done: 0, failed: 0, remaining: 0 },
          error: null,
        },
        201,
      ),
    );
    const view = await bulkExtractionApi.startCorpusPass("n1");
    expect(view.job_id).toBe("job-corpus");
  });

  it("startCorpusPass keeps the typed status for 422/409 rejections", async () => {
    raw.mockResolvedValueOnce(jsonResponse({ detail: "Corpus pass cannot start: …" }, 422));
    const err = await bulkExtractionApi.startCorpusPass("n1").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(BulkExtractionApiError);
    expect(err).toMatchObject({ status: 422 });
  });
});

describe("RULE-17 mirror parity — CorpusEstimate (schemas_corpus.py)", () => {
  it("CorpusEstimate mirrors CorpusEstimateView EXACTLY (8 fields)", () => {
    const estimate: CorpusEstimate = {
      total_chapters: 150,
      total_word_count: 150_000,
      selected_chapter_ids: ["0b6c8bd1-1111-4111-8111-111111111111"],
      chapter_count: 120,
      word_count: 120_000,
      ai_calls: 120,
      capped: true,
      cap_reason: "chapters",
    };
    expect(Object.keys(estimate).sort()).toEqual(Object.keys(CORPUS_ESTIMATE_FIELDS).sort());
  });

  it("cap_reason is the 'chapters' | 'words' | null literal union", () => {
    expect(Object.keys(CAP_REASON_PIN)).toEqual(["chapters", "words"]);
    const none: CorpusEstimate["cap_reason"] = null;
    expect(none).toBeNull();
  });

  it("ai_calls mirrors the D14a invariant (= chapter_count) in the fixture", () => {
    const estimate: CorpusEstimate = {
      total_chapters: 3,
      total_word_count: 9_000,
      selected_chapter_ids: [
        "0b6c8bd1-1111-4111-8111-111111111111",
        "0b6c8bd1-2222-4222-8222-222222222222",
        "0b6c8bd1-3333-4333-8333-333333333333",
      ],
      chapter_count: 3,
      word_count: 9_000,
      ai_calls: 3,
      capped: false,
      cap_reason: null,
    };
    expect(estimate.ai_calls).toBe(estimate.chapter_count);
    expect(estimate.capped).toBe(false);
  });
});
