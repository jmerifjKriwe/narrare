/**
 * useCorpusPassStart hook tests — corpus pass start/restart action (F3 T4).
 *
 * The real hook runs; only the transport boundary (`@/lib/api/bulkExtraction`)
 * is mocked (importOriginal spread so the REAL `BulkExtractionApiError`
 * class flows through and the typed 422 classification matches).
 *
 * Covered:
 * - success resolves the job id without an error,
 * - failure resolves null, keeps the raw error for classification and
 *   clears `isStarting`,
 * - a 422 rejection classifies as split-first (`isSplitFirst`),
 * - `clearError` drops a surfaced error.
 *
 * @module useCorpusPassStart.test
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const handle = vi.hoisted(() => ({
  startCorpusPass: vi.fn(),
}));

vi.mock("@/lib/api/bulkExtraction", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/bulkExtraction")>();
  return {
    ...actual,
    bulkExtractionApi: {
      startCorpusPass: handle.startCorpusPass,
    },
  };
});

import { BulkExtractionApiError } from "@/lib/api/bulkExtraction";
import { useCorpusPassStart } from "@/lib/hooks/useCorpusPassStart";

describe("useCorpusPassStart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("resolves the job id on success and surfaces no error", async () => {
    handle.startCorpusPass.mockResolvedValue({ job_id: "job-corpus-1" });
    const { result } = renderHook(() => useCorpusPassStart("novel-1"));

    let jobId: string | null = null;
    await act(async () => {
      jobId = await result.current.start();
    });

    expect(handle.startCorpusPass).toHaveBeenCalledWith("novel-1");
    expect(jobId).toBe("job-corpus-1");
    expect(result.current.startError).toBeNull();
    expect(result.current.isSplitFirst).toBe(false);
    expect(result.current.isStarting).toBe(false);
  });

  it("resolves null on failure and keeps the error for classification", async () => {
    handle.startCorpusPass.mockRejectedValue(new BulkExtractionApiError(409, "conflict"));
    const { result } = renderHook(() => useCorpusPassStart("novel-1"));

    let jobId: string | null = null;
    await act(async () => {
      jobId = await result.current.start();
    });

    expect(jobId).toBeNull();
    expect(result.current.startError).toBeInstanceOf(BulkExtractionApiError);
    expect(result.current.isSplitFirst).toBe(false);
    expect(result.current.isStarting).toBe(false);
  });

  it("classifies a 422 rejection as split-first", async () => {
    handle.startCorpusPass.mockRejectedValue(new BulkExtractionApiError(422, "split first"));
    const { result } = renderHook(() => useCorpusPassStart("novel-1"));

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.isSplitFirst).toBe(true);
  });

  it("clearError drops a surfaced error and re-arms the action", async () => {
    handle.startCorpusPass.mockRejectedValueOnce(new BulkExtractionApiError(409, "conflict"));
    const { result } = renderHook(() => useCorpusPassStart("novel-1"));

    await act(async () => {
      await result.current.start();
    });
    expect(result.current.startError).not.toBeNull();

    act(() => {
      result.current.clearError();
    });
    expect(result.current.startError).toBeNull();
    expect(result.current.isSplitFirst).toBe(false);
  });
});
