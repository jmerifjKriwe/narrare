/**
 * useBulkExtraction hook tests — bulk extraction job lifecycle (F2, ADR-092).
 *
 * The real hook lifecycle runs; only the transport boundary
 * (`@/lib/api/bulkExtraction`) is mocked. Fake timers drive the poll
 * cadence so the tests verify exactly the lifecycle behaviors that are
 * unique to this hook (plan Task 6):
 *
 * - polling starts when a job id is adopted (immediate first poll),
 * - polls on a fixed interval afterwards,
 * - never overlaps in-flight polls,
 * - stops on terminal job statuses, keeps polling through `cancelling`,
 * - stops on a 404 poll error (job gone = interrupted, spec §8.2) and
 *   exposes `isInterrupted`; other errors are transient,
 * - `reset()` halts the loop deliberately and clears all job state,
 * - a novelId change with a stale job 404s and halts — no endless polling,
 * - clears the interval on unmount,
 * - cancel/resume flow through the client and keep the status view as the
 *   single source of truth (job-view merge / poll-loop restart).
 *
 * @module useBulkExtraction.test
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Hoisted mock: the five bulk client methods, driven per-test. The real
// module is spread in so the REAL `BulkExtractionApiError` class flows
// through — the poll loop's `instanceof` check must match what tests throw.
const handle = vi.hoisted(() => ({
  start: vi.fn(),
  status: vi.fn(),
  results: vi.fn(),
  cancel: vi.fn(),
  resume: vi.fn(),
}));

vi.mock("@/lib/api/bulkExtraction", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/bulkExtraction")>();
  return {
    ...actual,
    bulkExtractionApi: {
      startBulkExtraction: handle.start,
      bulkJobStatus: handle.status,
      bulkJobResults: handle.results,
      cancelBulkJob: handle.cancel,
      resumeBulkJob: handle.resume,
    },
  };
});

import {
  type BulkChapterStatusView,
  BulkExtractionApiError,
  type BulkExtractionJobView,
  type BulkExtractionStatusView,
  type BulkJobStatus,
} from "@/lib/api/bulkExtraction";
import { useBulkExtraction } from "@/lib/hooks/useBulkExtraction";
import {
  BULK_EXTRACTION_POLL_INTERVAL_MS,
  isTerminalJobStatus,
} from "@/lib/hooks/useBulkExtractionPoll";

// ---------------------------------------------------------------------------
// Fixtures (mirroring schemas.py shapes — see bulkExtraction.test.ts parity)
// ---------------------------------------------------------------------------

const NOVEL = "n1";

function jobView(status: BulkJobStatus, jobId = "job-1"): BulkExtractionJobView {
  return {
    job_id: jobId,
    novel_id: NOVEL,
    status,
    created_at: "2026-10-03T10:00:00Z",
    updated_at: "2026-10-03T10:01:00Z",
    totals: { total: 3, done: 1, failed: 0, remaining: 2 },
    error: null,
  };
}

function chapterRow(overrides: Partial<BulkChapterStatusView> = {}): BulkChapterStatusView {
  return {
    chapter_id: "c1",
    title: "Storm",
    position: 12,
    state: "done",
    item_count: 9,
    error: null,
    ...overrides,
  };
}

function statusView(
  status: BulkJobStatus,
  chapters: BulkChapterStatusView[] = [chapterRow()],
  jobId = "job-1",
): BulkExtractionStatusView {
  return { ...jobView(status, jobId), chapters, dedup: null };
}

/** Deferred promise for the in-flight (no-overlap) test. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

/** Settle pending poll continuations without advancing the interval. */
const flush = () => act(async () => void (await vi.advanceTimersByTimeAsync(0)));

/** Advance exactly one poll interval. */
const tick = () =>
  act(async () => void (await vi.advanceTimersByTimeAsync(BULK_EXTRACTION_POLL_INTERVAL_MS)));

async function startJob(hook: { current: ReturnType<typeof useBulkExtraction> }) {
  await act(async () => {
    await hook.current.start(["c1", "c2"]);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  handle.start.mockResolvedValue(jobView("pending"));
  handle.status.mockResolvedValue(statusView("running"));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useBulkExtraction", () => {
  it("start posts chapter ids, adopts the job id, and polls status immediately", async () => {
    const { result } = renderHook(() => useBulkExtraction(NOVEL));

    expect(result.current.jobId).toBeNull();
    const view = await act(() => result.current.start(["c1", "c2"]));

    expect(handle.start).toHaveBeenCalledWith(NOVEL, ["c1", "c2"]);
    expect(view?.job_id).toBe("job-1");
    expect(result.current.jobId).toBe("job-1");
    // Immediate first poll — progress is visible without waiting a cadence.
    expect(handle.status).toHaveBeenCalledTimes(1);
    expect(handle.status).toHaveBeenCalledWith(NOVEL, "job-1");

    await flush();
    expect(result.current.status?.status).toBe("running");
  });

  it("polls on the interval cadence while the job is active", async () => {
    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    expect(handle.status).toHaveBeenCalledTimes(1);

    await tick();
    expect(handle.status).toHaveBeenCalledTimes(2);

    await tick();
    expect(handle.status).toHaveBeenCalledTimes(3);
  });

  it("never overlaps polls while a status request is in flight", async () => {
    const pending = deferred<BulkExtractionStatusView>();
    handle.status.mockImplementation(() => pending.promise);

    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    expect(handle.status).toHaveBeenCalledTimes(1); // immediate poll, in flight

    // Four cadences elapse while the first poll is still unresolved —
    // each tick must be skipped by the in-flight guard.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(BULK_EXTRACTION_POLL_INTERVAL_MS * 4);
    });
    expect(handle.status).toHaveBeenCalledTimes(1);

    pending.resolve(statusView("running"));
    await flush();
    expect(result.current.status?.status).toBe("running");

    await tick();
    expect(handle.status).toHaveBeenCalledTimes(2);
  });

  it("stops polling when the job reaches a terminal status", async () => {
    handle.status.mockResolvedValue(statusView("completed"));
    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    await flush();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(BULK_EXTRACTION_POLL_INTERVAL_MS * 3);
    });
    expect(handle.status).toHaveBeenCalledTimes(1); // no cadence polls after terminal
    expect(isTerminalJobStatus(result.current.status!.status)).toBe(true);
  });

  it("keeps polling while the job is cancelling (non-terminal)", async () => {
    handle.status.mockResolvedValue(statusView("cancelling"));
    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    expect(handle.status).toHaveBeenCalledTimes(1);

    await tick();
    await tick();
    expect(handle.status).toHaveBeenCalledTimes(3);
  });

  it.each(["completed", "cancelled", "failed"] as const)(
    "treats %s as terminal for poll lifecycle",
    async (status) => {
      handle.status.mockResolvedValue(statusView(status));
      const { result } = renderHook(() => useBulkExtraction(NOVEL));
      await startJob(result);
      await flush();

      await tick();
      await tick();
      expect(handle.status).toHaveBeenCalledTimes(1);
      expect(result.current.isActive).toBe(false);
    },
  );

  it("clears the interval on unmount", async () => {
    const { result, unmount } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    expect(handle.status).toHaveBeenCalledTimes(1);

    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(BULK_EXTRACTION_POLL_INTERVAL_MS * 3);
    });
    expect(handle.status).toHaveBeenCalledTimes(1);
  });

  it("surfaces transient poll errors and keeps polling; success clears the error", async () => {
    handle.status
      .mockRejectedValueOnce(new Error("network blip"))
      .mockResolvedValueOnce(statusView("running"));

    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    await flush();
    expect(result.current.error).toBe("network blip");

    await tick();
    expect(handle.status).toHaveBeenCalledTimes(2);
    expect(result.current.error).toBeNull();
    expect(result.current.status?.status).toBe("running");
  });

  it("keeps polling on non-404 API errors (only a 404 means interrupted)", async () => {
    handle.status
      .mockRejectedValueOnce(new BulkExtractionApiError(500, "boom"))
      .mockResolvedValueOnce(statusView("running"));

    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    await flush();
    expect(result.current.error).toBe("boom");
    expect(result.current.isInterrupted).toBe(false);

    await tick();
    expect(handle.status).toHaveBeenCalledTimes(2);
    expect(result.current.status?.status).toBe("running");
  });

  it("stops the loop and flags isInterrupted when a poll 404s (job gone)", async () => {
    handle.status.mockRejectedValue(
      new BulkExtractionApiError(404, "Bulk extraction job not found"),
    );

    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    await flush();
    expect(handle.status).toHaveBeenCalledTimes(1);
    expect(result.current.isInterrupted).toBe(true);
    expect(result.current.isActive).toBe(false);
    expect(result.current.error).toBe("Bulk extraction job not found");

    // The loop halted: cadence ticks produce no further polls.
    await tick();
    await tick();
    expect(handle.status).toHaveBeenCalledTimes(1);
  });

  it("reset() halts polling deliberately and clears all job state", async () => {
    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    await flush();
    expect(handle.status).toHaveBeenCalledTimes(1);
    expect(result.current.isActive).toBe(true);

    await act(async () => {
      result.current.reset();
    });

    expect(result.current.jobId).toBeNull();
    expect(result.current.status).toBeNull();
    expect(result.current.isActive).toBe(false);
    expect(result.current.isInterrupted).toBe(false);

    // Halted for good: cadence ticks produce no further polls.
    await tick();
    await tick();
    expect(handle.status).toHaveBeenCalledTimes(1);
  });

  it("a novelId change with a stale job 404s and halts instead of polling forever", async () => {
    const { result, rerender } = renderHook(
      ({ novelId }: { novelId: string }) => useBulkExtraction(novelId),
      { initialProps: { novelId: NOVEL } },
    );
    await startJob(result); // job-1 adopted on n1
    await flush();
    expect(handle.status).toHaveBeenCalledTimes(1);

    // The job registry is in-memory per backend process — a server restart
    // (or a novelId change binding the stale job to the wrong novel) 404s.
    handle.status.mockRejectedValue(
      new BulkExtractionApiError(404, "Bulk extraction job not found"),
    );
    rerender({ novelId: "n2" });
    await flush();
    // The re-run polled once with the new novel id, got 404, and stopped.
    expect(handle.status).toHaveBeenCalledTimes(2);
    expect(handle.status).toHaveBeenLastCalledWith("n2", "job-1");
    expect(result.current.isInterrupted).toBe(true);

    await tick();
    await tick();
    expect(handle.status).toHaveBeenCalledTimes(2);
  });

  it("cancel posts through the client and merges the job view into the status view", async () => {
    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    await flush();
    const chaptersBefore = result.current.chapters;

    handle.cancel.mockResolvedValue(jobView("cancelling"));
    await act(async () => {
      await result.current.cancel();
    });

    expect(handle.cancel).toHaveBeenCalledWith(NOVEL, "job-1");
    expect(result.current.status?.status).toBe("cancelling");
    // The cancel response carries no chapter rows — the last polled rows stay.
    expect(result.current.chapters).toEqual(chaptersBefore);
    // cancelling is non-terminal: polling continues.
    await tick();
    expect(handle.status).toHaveBeenCalledTimes(2);
  });

  it("resume posts, merges the view, and restarts polling after a terminal status", async () => {
    handle.status.mockResolvedValue(statusView("failed"));
    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    await flush();
    expect(handle.status).toHaveBeenCalledTimes(1); // terminal → poll stopped

    handle.resume.mockResolvedValue(jobView("pending"));
    // Server state after the reset: chapters re-pended, runner dispatched.
    handle.status.mockResolvedValue(statusView("running"));
    await act(async () => {
      await result.current.resume();
    });

    expect(handle.resume).toHaveBeenCalledWith(NOVEL, "job-1");
    // Same job id — the poll loop restarts for it (immediate poll + cadence)
    // and the re-poll reflects the server state after the reset.
    expect(handle.status).toHaveBeenCalledTimes(2);
    await tick();
    expect(handle.status).toHaveBeenCalledTimes(3);
    expect(result.current.status?.status).toBe("running");
    expect(result.current.isActive).toBe(true);
  });

  it("start resets the previous job's status view and error", async () => {
    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    await flush();
    expect(result.current.status).not.toBeNull();

    handle.start.mockResolvedValue(jobView("pending", "job-2"));
    handle.status.mockResolvedValue(statusView("running", [chapterRow()], "job-2"));
    await act(async () => {
      await result.current.start(["c3"]);
    });
    await flush();

    expect(result.current.jobId).toBe("job-2");
    expect(result.current.status?.job_id).toBe("job-2");
    expect(result.current.error).toBeNull();
  });

  it("exposes per-chapter rows, totals, and the active flag", async () => {
    handle.status.mockResolvedValue(
      statusView("running", [
        chapterRow({ chapter_id: "c1", state: "done", item_count: 4 }),
        chapterRow({
          chapter_id: "c2",
          title: "Aftermath",
          position: 13,
          state: "running",
          item_count: null,
        }),
        chapterRow({
          chapter_id: "c3",
          title: "Coda",
          position: 14,
          state: "pending",
          item_count: null,
        }),
      ]),
    );

    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    await flush();

    expect(result.current.chapters).toHaveLength(3);
    expect(result.current.totals).toEqual({ total: 3, done: 1, failed: 0, remaining: 2 });
    expect(result.current.isActive).toBe(true);
    expect(result.current.isStarting).toBe(false);
  });

  it("reports the start error and adopts no job when start fails", async () => {
    handle.start.mockRejectedValueOnce(
      new Error("A bulk extraction job is already active for this novel"),
    );
    const { result } = renderHook(() => useBulkExtraction(NOVEL));

    const view = await act(() => result.current.start(["c1"]));

    expect(view).toBeNull();
    expect(result.current.jobId).toBeNull();
    expect(result.current.error).toBe("A bulk extraction job is already active for this novel");
    expect(handle.status).not.toHaveBeenCalled();
  });

  // --- F3 corpus pass (plan Task 4): adopt a PRE-started corpus job --------

  it("adopt() attaches a pre-started job id and polls immediately without calling start", async () => {
    const { result } = renderHook(() => useBulkExtraction(NOVEL));

    await act(async () => {
      result.current.adopt("job-corpus");
    });
    await flush();

    expect(result.current.jobId).toBe("job-corpus");
    // The corpus job already exists server-side — adopt must NOT start one.
    expect(handle.start).not.toHaveBeenCalled();
    // Immediate first poll, then the cadence — the adopted job is live.
    expect(handle.status).toHaveBeenCalledTimes(1);
    expect(handle.status).toHaveBeenCalledWith(NOVEL, "job-corpus");
    expect(result.current.isActive).toBe(true);

    await tick();
    expect(handle.status).toHaveBeenCalledTimes(2);
  });

  it("adopt() replaces a previous job's state (no stale status bleed-through)", async () => {
    const { result } = renderHook(() => useBulkExtraction(NOVEL));
    await startJob(result);
    await flush();
    expect(result.current.status?.job_id).toBe("job-1");

    // The adopted job's own poll results (fixture carries its id).
    handle.status.mockResolvedValue(statusView("running", [chapterRow()], "job-corpus"));
    await act(async () => {
      result.current.adopt("job-corpus");
    });
    await flush();

    expect(result.current.jobId).toBe("job-corpus");
    expect(result.current.status?.job_id).toBe("job-corpus");
    expect(result.current.isInterrupted).toBe(false);
  });
});
