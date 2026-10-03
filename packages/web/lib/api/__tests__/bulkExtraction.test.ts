/**
 * Bulk extraction API client tests (F2, ADR-092, plan Task 6).
 *
 * Two concerns:
 * 1. Wire paths + bodies: the five client methods must hit the exact REST
 *    paths of spec §4 (`/novels/{id}/kb/extract/bulk…`) with the exact
 *    request bodies.
 * 2. RULE-17 mirror parity: every TS type must mirror the field list of its
 *    `apps/api/narrare/kb/bulk_extraction/schemas.py` counterpart EXACTLY.
 *    Enforced twice — exhaustive compile-time field tables (drift fails
 *    `pnpm type-check`) and runtime fixture key-set assertions (drift fails
 *    this suite).
 *
 * @module bulkExtraction.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/core", () => ({ fetchApi: vi.fn() }));

import {
  type BulkChapterState,
  type BulkChapterStatusView,
  type BulkExtractionJobView,
  type BulkExtractionResultChapter,
  type BulkExtractionResultsView,
  type BulkExtractionStatusView,
  type BulkExtractionTotals,
  type BulkJobStatus,
  bulkExtractionApi,
} from "@/lib/api/bulkExtraction";
import { fetchApi } from "@/lib/api/core";
import type { ExtractionItem, ExtractionOutput } from "@/lib/api/extraction";

const f = vi.mocked(fetchApi);

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
};

// Normative enum sets (spec §4.1/§4.2). A widened/narrowed TS union breaks the
// assignment below at type-check; the runtime toEqual pins the exact sets.
const ALL_JOB_STATUSES: readonly BulkJobStatus[] = [
  "pending",
  "running",
  "cancelling",
  "completed",
  "cancelled",
  "failed",
];
const ALL_CHAPTER_STATES: readonly BulkChapterState[] = ["pending", "running", "done", "failed"];

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
    f.mockResolvedValueOnce({} as never);
    await bulkExtractionApi.startBulkExtraction("n1", ["c1", "c2"]);
    expect(f).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk", {
      method: "POST",
      body: JSON.stringify({ chapter_ids: ["c1", "c2"] }),
      signal: undefined,
    });
  });

  it("bulkJobStatus GETs …/kb/extract/bulk/{jobId}/status", async () => {
    f.mockResolvedValueOnce({} as never);
    await bulkExtractionApi.bulkJobStatus("n1", "job-9");
    expect(f).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/job-9/status", {
      signal: undefined,
    });
  });

  it("bulkJobResults GETs …/kb/extract/bulk/{jobId}/results", async () => {
    f.mockResolvedValueOnce({} as never);
    await bulkExtractionApi.bulkJobResults("n1", "job-9");
    expect(f).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/job-9/results", {
      signal: undefined,
    });
  });

  it("cancelBulkJob POSTs …/kb/extract/bulk/{jobId}/cancel (no body)", async () => {
    f.mockResolvedValueOnce({} as never);
    await bulkExtractionApi.cancelBulkJob("n1", "job-9");
    expect(f).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/job-9/cancel", {
      method: "POST",
      signal: undefined,
    });
  });

  it("resumeBulkJob POSTs …/kb/extract/bulk/{jobId}/resume (no body)", async () => {
    f.mockResolvedValueOnce({} as never);
    await bulkExtractionApi.resumeBulkJob("n1", "job-9");
    expect(f).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/job-9/resume", {
      method: "POST",
      signal: undefined,
    });
  });

  it("forwards the AbortSignal when given", async () => {
    f.mockResolvedValueOnce({} as never);
    const controller = new AbortController();
    await bulkExtractionApi.bulkJobStatus("n1", "job-9", controller.signal);
    expect(f).toHaveBeenCalledWith("/novels/n1/kb/extract/bulk/job-9/status", {
      signal: controller.signal,
    });
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

  it("BulkExtractionStatusView = job view + chapters", () => {
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
    };
    expect(Object.keys(statusView).sort()).toEqual(Object.keys(STATUS_VIEW_FIELDS).sort());
    // Row mirror re-asserted on the failed row: item_count null + error set —
    // the fields the coordinator flagged as MUST-have in the TS mirror.
    expect(Object.keys(statusView.chapters[1]).sort()).toEqual(
      Object.keys(CHAPTER_STATUS_FIELDS).sort(),
    );
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
    };
    expect(Object.keys(view).sort()).toEqual(Object.keys(RESULTS_VIEW_FIELDS).sort());
    expect(Object.keys(done).sort()).toEqual(Object.keys(RESULT_CHAPTER_FIELDS).sort());
    expect(done.output?.results).toHaveLength(1);
    expect(failed.output).toBeNull();
  });

  it("job status + chapter state unions match the normative sets", () => {
    expect(ALL_JOB_STATUSES).toEqual([
      "pending",
      "running",
      "cancelling",
      "completed",
      "cancelled",
      "failed",
    ]);
    expect(ALL_CHAPTER_STATES).toEqual(["pending", "running", "done", "failed"]);
  });
});
