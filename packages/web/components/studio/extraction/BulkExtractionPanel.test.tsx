/**
 * BulkExtractionPanel tests — progress, review reuse, walking (F2 T7, ADR-092).
 *
 * The real component tree runs (BulkExtractionPanel + BulkChapterReview +
 * ExtractionReview + the real useBulkExtraction poll hook + the real
 * useApplyExtraction apply hook); only the transport boundary is mocked:
 *
 * - `@/lib/api/bulkExtraction` — the five bulk client methods (the REAL
 *   `BulkExtractionApiError` class flows through via importOriginal spread,
 *   so the poll loop's instanceof 404 check matches what tests throw),
 * - `@/lib/api/extraction` — only `applyExtraction` is replaced, so the test
 *   asserts the real hook wiring (`{ items, chapter_id }` provenance).
 *
 * next-intl serves the REAL "en" studio catalog (per-file real-catalog
 * pattern, same as ImportModal.test.tsx) so tests assert rendered copy.
 *
 * Covered (plan Task 7):
 * 1. auto-start on mount + progress rendering from a status fixture,
 * 2. polling stops on `completed` and review mode is entered,
 * 3. cancel → `cancelling` chip state → terminal cancelled banner,
 * 4. 404 status → interrupted copy + restart via reset()+start,
 * 5. review mode renders ExtractionReview for the first done chapter,
 * 6. apply sends the selected items with the chapter id,
 * 7. next-unreviewed walking advances past an applied chapter,
 * 8. resume appears for cancelled|failed and re-polls,
 * 9. skip marks a chapter and walking passes it.
 *
 * @module BulkExtractionPanel.test
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BulkExtractionPanel } from "./BulkExtractionPanel";

// ---------------------------------------------------------------------------
// next-intl — REAL "en" studio catalog (real-catalog pattern)
// ---------------------------------------------------------------------------

vi.mock("next-intl", async () => {
  const actual = await vi.importActual<typeof import("next-intl")>("next-intl");
  const studio = (await import("../../../../i18n/messages/en/studio.json")).default;
  return {
    ...actual,
    useTranslations: () =>
      actual.createTranslator({ locale: "en", messages: { studio }, namespace: "studio" }),
  };
});

// ---------------------------------------------------------------------------
// Transport mocks — real hooks run against fake clients
// ---------------------------------------------------------------------------

const handle = vi.hoisted(() => ({
  start: vi.fn(),
  status: vi.fn(),
  results: vi.fn(),
  cancel: vi.fn(),
  resume: vi.fn(),
  apply: vi.fn(),
  corpusStart: vi.fn(),
  resolutionList: vi.fn(),
  resolutionAnalyze: vi.fn(),
  resolutionEndorse: vi.fn(),
  resolutionReject: vi.fn(),
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
      startCorpusPass: handle.corpusStart,
    },
  };
});

vi.mock("@/lib/api/extraction", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/extraction")>();
  return {
    ...actual,
    extractionApi: {
      ...actual.extractionApi,
      applyExtraction: handle.apply,
    },
  };
});

vi.mock("@/lib/api/kbResolution", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/kbResolution")>();
  return {
    ...actual,
    kbResolutionApi: {
      listSuggestions: handle.resolutionList,
      analyzeSuggestions: handle.resolutionAnalyze,
      endorseSuggestion: handle.resolutionEndorse,
      rejectSuggestion: handle.resolutionReject,
    },
  };
});

import {
  type BulkChapterStatusView,
  type BulkDedupInfo,
  BulkExtractionApiError,
  type BulkExtractionResultsView,
  type BulkExtractionStatusView,
  type BulkJobStatus,
} from "@/lib/api/bulkExtraction";
import type { ExtractionOutput } from "@/lib/api/extraction";
import type { ResolutionAnalysisResponse } from "@/lib/api/kbResolution";

// ---------------------------------------------------------------------------
// Fixtures (same shapes as the useBulkExtraction hook test)
// ---------------------------------------------------------------------------

const NOVEL = "novel-1";
const CHAPTER_IDS = ["c1", "c2", "c3", "c4"];

function jobView(status: BulkJobStatus, jobId = "job-1", error: string | null = null) {
  return {
    job_id: jobId,
    novel_id: NOVEL,
    status,
    created_at: "2026-10-03T10:00:00Z",
    updated_at: "2026-10-03T10:01:00Z",
    totals: { total: 4, done: 1, failed: 1, remaining: 2 },
    error,
  };
}

function chapterRow(overrides: Partial<BulkChapterStatusView> = {}): BulkChapterStatusView {
  return {
    chapter_id: "c1",
    title: "Storm",
    position: 12,
    state: "done",
    item_count: 4,
    error: null,
    ...overrides,
  };
}

/** One done + one running + one pending + one failed row (progress fixture). */
function fourChapters(): BulkChapterStatusView[] {
  return [
    chapterRow(),
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
    chapterRow({
      chapter_id: "c4",
      title: "Echoes",
      position: 15,
      state: "failed",
      item_count: null,
      error: "LLM timeout",
    }),
  ];
}

/** Two done + one pending row (review fixture — walking over done chapters). */
function twoDoneChapters(): BulkChapterStatusView[] {
  return [
    chapterRow(),
    chapterRow({
      chapter_id: "c2",
      title: "Aftermath",
      position: 13,
      state: "done",
      item_count: 2,
    }),
    chapterRow({
      chapter_id: "c3",
      title: "Coda",
      position: 14,
      state: "pending",
      item_count: null,
    }),
  ];
}

/** Three done + one pending row (walking-path fixture — T8 rider a). */
function threeDoneChapters(): BulkChapterStatusView[] {
  return [
    chapterRow(),
    chapterRow({
      chapter_id: "c2",
      title: "Aftermath",
      position: 13,
      state: "done",
      item_count: 2,
    }),
    chapterRow({
      chapter_id: "c3",
      title: "Coda",
      position: 14,
      state: "done",
      item_count: 3,
    }),
    chapterRow({
      chapter_id: "c4",
      title: "Echoes",
      position: 15,
      state: "pending",
      item_count: null,
    }),
  ];
}

function statusView(
  status: BulkJobStatus,
  chapters: BulkChapterStatusView[],
  jobId = "job-1",
  error: string | null = null,
  dedup: BulkDedupInfo | null = null,
): BulkExtractionStatusView {
  const done = chapters.filter((c) => c.state === "done").length;
  const failed = chapters.filter((c) => c.state === "failed").length;
  return {
    ...jobView(status, jobId, error),
    totals: {
      total: chapters.length,
      done,
      failed,
      remaining: chapters.length - done - failed,
    },
    chapters,
    dedup,
  };
}

function outputFor(name: string, itemType: "new_entity" | "update_entity"): ExtractionOutput {
  return {
    results: [
      {
        item_type: itemType,
        entity_type: "character",
        name,
        confidence: 0.9,
        source_text: `Source text mentioning ${name}.`,
        proposed_content: null,
        target_entity_id: itemType === "update_entity" ? "kb-entry-2" : null,
        conflict_description: null,
        relationship_type: null,
        related_entity_name: null,
      },
    ],
    analysis_notes: `Notes for ${name}.`,
  };
}

function resultsView(
  status: BulkJobStatus,
  chapters: BulkChapterStatusView[],
): BulkExtractionResultsView {
  // One distinguishable entity name per done chapter, so tests can assert
  // WHICH chapter's review body is mounted.
  const names: Record<string, string> = {
    c1: "Anna Schmidt",
    c2: "Dr. Viktor Stein",
    c3: "Marcus Weber",
  };
  return {
    job_id: "job-1",
    novel_id: NOVEL,
    status,
    dedup: null,
    chapters: chapters.map((c) => ({
      chapter_id: c.chapter_id,
      title: c.title,
      position: c.position,
      state: c.state,
      output:
        c.state === "done"
          ? outputFor(
              names[c.chapter_id] ?? "Dr. Viktor Stein",
              c.chapter_id === "c2" ? "update_entity" : "new_entity",
            )
          : null,
    })),
  };
}

// ---------------------------------------------------------------------------
// Render helpers (fake timers drive the poll cadence)
// ---------------------------------------------------------------------------

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderPanel() {
  const onClose = vi.fn();
  render(
    <QueryClientProvider client={createQueryClient()}>
      <BulkExtractionPanel novelId={NOVEL} chapterIds={CHAPTER_IDS} onClose={onClose} />
    </QueryClientProvider>,
  );
  return { onClose };
}

/** Drain the microtask/timer chain twice (start → poll / query fetches). */
const settle = async () => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(0);
  });
};

/** Render with a running job: mount auto-start + immediate poll resolved. */
async function renderStarted(status: BulkExtractionStatusView) {
  handle.status.mockResolvedValue(status);
  handle.results.mockResolvedValue(resultsView(status.status, status.chapters));
  renderPanel();
  await settle();
}

beforeEach(() => {
  // Fake ONLY the timer functions — vitest's default also fakes
  // queueMicrotask, which stalls useAIOperation.start() (its invokeExecute
  // is queued via queueMicrotask) and with it the whole apply flow.
  vi.useFakeTimers({
    toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"],
  });
  vi.clearAllMocks();
  handle.start.mockResolvedValue(jobView("pending"));
  handle.status.mockResolvedValue(statusView("running", fourChapters()));
  handle.results.mockResolvedValue(resultsView("running", fourChapters()));
  handle.cancel.mockResolvedValue(jobView("cancelling"));
  handle.resume.mockResolvedValue(jobView("pending"));
  handle.apply.mockResolvedValue({ created_entries: [], updated_entries: [] });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BulkExtractionPanel", () => {
  it("starts the job on mount and renders totals, state chips, item counts and errors", async () => {
    expect(handle.start).not.toHaveBeenCalled();
    await renderStarted(statusView("running", fourChapters()));

    expect(handle.start).toHaveBeenCalledTimes(1);
    expect(handle.start).toHaveBeenCalledWith(NOVEL, CHAPTER_IDS);
    expect(handle.status).toHaveBeenCalledWith(NOVEL, "job-1");

    // Totals summary + shared-budget cost note (D7a, honest copy)
    expect(screen.getByText("1 of 4 chapters")).toBeInTheDocument();
    expect(screen.getByText(/4 AI calls, one per chapter/)).toBeInTheDocument();

    // Per-chapter rows: title + state chip (+ item_count when done, error when failed)
    expect(screen.getByText("Storm")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("4 items found")).toBeInTheDocument();
    expect(screen.getByText("LLM timeout")).toBeInTheDocument();
  });

  it("stops polling once the job completes and enters review mode", async () => {
    await renderStarted(statusView("completed", twoDoneChapters()));

    expect(screen.getByText("Review extracted knowledge")).toBeInTheDocument();
    expect(handle.status).toHaveBeenCalledTimes(1); // immediate poll only

    await act(async () => {
      await vi.advanceTimersByTimeAsync(7000);
    });
    expect(handle.status).toHaveBeenCalledTimes(1); // terminal → cadence stopped
  });

  it("cancel shows the cancelling state until the poll observes cancelled", async () => {
    await renderStarted(statusView("running", fourChapters()));

    fireEvent.click(screen.getByRole("button", { name: "Cancel extraction" }));
    await settle();

    expect(handle.cancel).toHaveBeenCalledWith(NOVEL, "job-1");
    expect(screen.getByRole("button", { name: "Cancelling…" })).toBeDisabled();

    // Next cadence poll observes `cancelled` → terminal banner in review mode.
    handle.status.mockResolvedValue(statusView("cancelled", fourChapters()));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    await settle();
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();
  });

  it("shows the interrupted state on a 404 poll and restarts via reset + start", async () => {
    handle.status.mockRejectedValue(
      new BulkExtractionApiError(404, "Bulk extraction job not found"),
    );
    renderPanel();
    await settle();

    expect(screen.getByText("Extraction job interrupted")).toBeInTheDocument();
    expect(screen.getByText(/Nothing has been written to your Knowledge Base/)).toBeInTheDocument();

    handle.start.mockClear();
    handle.status.mockResolvedValue(statusView("running", fourChapters()));
    fireEvent.click(screen.getByRole("button", { name: "Start over" }));
    await settle();

    expect(handle.start).toHaveBeenCalledTimes(1); // restart creates a NEW job
    expect(handle.start).toHaveBeenCalledWith(NOVEL, CHAPTER_IDS);
    expect(screen.getByText("1 of 4 chapters")).toBeInTheDocument(); // progress again
  });

  it("review mode renders ExtractionReview for the first done chapter", async () => {
    await renderStarted(statusView("completed", twoDoneChapters()));
    await settle(); // results query

    expect(handle.results).toHaveBeenCalledWith(NOVEL, "job-1", expect.anything());
    // ExtractionReview reused verbatim: summary bar + item card of chapter c1
    // ("{count} items found" catalog string — no plural form, by design)
    expect(screen.getByText("1 items found")).toBeInTheDocument();
    expect(screen.getByText("Anna Schmidt")).toBeInTheDocument();
    // Chapter rail ordered by position, active chapter marked
    expect(screen.getByRole("button", { name: /Storm/ })).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("button", { name: /Aftermath/ })).toBeInTheDocument();
  });

  it("apply sends the selected items with the chapter id for provenance", async () => {
    await renderStarted(statusView("completed", twoDoneChapters()));
    await settle();

    fireEvent.click(screen.getByRole("button", { name: "Apply to Knowledge Base" }));
    await settle();

    expect(handle.apply).toHaveBeenCalledTimes(1);
    const [novelId, items, chapterId] = handle.apply.mock.calls[0];
    expect(novelId).toBe(NOVEL);
    expect(chapterId).toBe("c1");
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      item_type: "new_entity",
      name: "Anna Schmidt",
      entity_type: "character",
    });

    await settle();
    expect(screen.getByText("Applied")).toBeInTheDocument(); // rail badge
  });

  it("next-unreviewed walking advances past an applied chapter", async () => {
    await renderStarted(statusView("completed", twoDoneChapters()));
    await settle();

    // Apply chapter c1 → it becomes reviewed (applied badge)
    fireEvent.click(screen.getByRole("button", { name: "Apply to Knowledge Base" }));
    await settle();
    expect(screen.getByText("Applied")).toBeInTheDocument();

    // Next chapter walks FORWARD past the applied one → c2's review body
    fireEvent.click(screen.getByRole("button", { name: "Next chapter" }));
    await settle();

    expect(screen.getByText("Dr. Viktor Stein")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Aftermath/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.getByRole("button", { name: /Storm/ })).not.toHaveAttribute("aria-current");
  });

  it("offers resume for a cancelled job and re-enters progress mode on resume", async () => {
    await renderStarted(statusView("cancelled", twoDoneChapters()));
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(handle.status).toHaveBeenCalledTimes(1); // terminal → no cadence polls

    // The resume re-poll must observe the POST-resume server state.
    handle.status.mockResolvedValue(statusView("running", twoDoneChapters()));
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    await settle();

    expect(handle.resume).toHaveBeenCalledWith(NOVEL, "job-1");
    expect(handle.status).toHaveBeenCalledTimes(2); // epoch bump → immediate re-poll
    expect(screen.getByText("2 of 3 chapters")).toBeInTheDocument(); // progress mode
  });

  it("offers resume for a failed job with the failure reason", async () => {
    await renderStarted(statusView("failed", fourChapters(), "job-1", "Provider not configured"));
    expect(screen.getByText("Provider not configured")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();
  });

  it("skip marks a chapter and walking passes it", async () => {
    await renderStarted(statusView("completed", twoDoneChapters()));
    await settle();

    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    await settle();

    expect(screen.getByText("Skipped")).toBeInTheDocument(); // rail badge

    fireEvent.click(screen.getByRole("button", { name: "Next chapter" }));
    await settle();
    expect(screen.getByText("Dr. Viktor Stein")).toBeInTheDocument();
  });

  // -- T8 review riders -----------------------------------------------------

  it("walking path over ≥3 done chapters: rail-click mid-list, next-unreviewed, Next disabled at the end", async () => {
    await renderStarted(statusView("completed", threeDoneChapters()));
    await settle();

    // First done chapter is active on entry.
    expect(screen.getByRole("button", { name: /Storm/ })).toHaveAttribute("aria-current", "true");
    expect(screen.getByText("Anna Schmidt")).toBeInTheDocument();

    // Rail-click mid-list → that chapter's review body mounts (c2, not c1).
    fireEvent.click(screen.getByRole("button", { name: /Aftermath/ }));
    await settle();
    expect(screen.getByRole("button", { name: /Aftermath/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.getByText("Dr. Viktor Stein")).toBeInTheDocument();

    // Apply c2 → reviewed; Next walks FORWARD to the next unreviewed done (c3).
    fireEvent.click(screen.getByRole("button", { name: "Apply to Knowledge Base" }));
    await settle();
    expect(screen.getByText("Applied")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next chapter" }));
    await settle();
    expect(screen.getByText("Marcus Weber")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Coda/ })).toHaveAttribute("aria-current", "true");

    // Apply c3 → nothing unreviewed remains after it → Next disabled.
    fireEvent.click(screen.getByRole("button", { name: "Apply to Knowledge Base" }));
    await settle();
    expect(screen.getAllByText("Applied")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Next chapter" })).toBeDisabled();
  });

  it("clears a failed apply's error when switching chapters (per-chapter remount)", async () => {
    await renderStarted(statusView("completed", twoDoneChapters()));
    await settle();

    // The apply path routes failures through useAIOperation's error mapper,
    // which rewrites the message — assert the ALERT, not its wording.
    handle.apply.mockRejectedValueOnce(new Error("provider down"));
    fireEvent.click(screen.getByRole("button", { name: "Apply to Knowledge Base" }));
    await settle();
    expect(screen.getByRole("alert")).toBeInTheDocument();

    // Rail-click to another chapter — the stale error must NOT follow the user.
    fireEvent.click(screen.getByRole("button", { name: /Aftermath/ }));
    await settle();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    // Fresh review body: apply is enabled again with the new chapter's items.
    expect(screen.getByRole("button", { name: "Apply to Knowledge Base" })).toBeEnabled();
  });

  it("shows a dedicated loading state while results load (not the job-start copy)", async () => {
    handle.status.mockResolvedValue(statusView("completed", twoDoneChapters()));
    handle.results.mockReturnValue(new Promise(() => {}));
    renderPanel();
    await settle();

    expect(screen.getByText("Loading results…")).toBeInTheDocument();
    expect(screen.queryByText("Starting extraction…")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// F3 corpus pass (plan Task 4): the panel hosts a PRE-started corpus job via
// the optional initialJobId prop — adopted instead of started, restarted via
// the corpus endpoint, and the cost note never lies about an unknown count.
// ---------------------------------------------------------------------------

describe("BulkExtractionPanel corpus adoption (F3 T4)", () => {
  /** Render the panel in corpus mode (adopted job, empty explicit seed). */
  function renderCorpusPanel(initialJobId = "job-corpus") {
    render(
      <QueryClientProvider client={createQueryClient()}>
        <BulkExtractionPanel
          novelId={NOVEL}
          chapterIds={[]}
          initialJobId={initialJobId}
          onClose={vi.fn()}
        />
      </QueryClientProvider>,
    );
  }

  it("adopts the corpus job on mount WITHOUT starting an explicit job", async () => {
    handle.status.mockResolvedValue(statusView("running", fourChapters(), "job-corpus"));
    renderCorpusPanel();

    // Before the first poll resolves: no totals, and the cost note must NOT
    // render a fallback count for an adopted job (there is no seed — "0 AI
    // calls" would be a lie).
    expect(screen.queryByText(/AI calls, one per chapter/)).not.toBeInTheDocument();

    await settle();
    expect(handle.start).not.toHaveBeenCalled();
    expect(handle.status).toHaveBeenCalledWith(NOVEL, "job-corpus");
    // Totals arrived → the D7a cost note renders with the POLLED count.
    expect(screen.getByText(/4 AI calls, one per chapter/)).toBeInTheDocument();
  });

  it("restarts an interrupted corpus job via the corpus endpoint, not an explicit start", async () => {
    handle.status
      .mockRejectedValueOnce(new BulkExtractionApiError(404, "Bulk extraction job not found"))
      .mockResolvedValue(statusView("running", fourChapters(), "job-corpus-2"));
    handle.corpusStart.mockResolvedValue(jobView("pending", "job-corpus-2"));
    renderCorpusPanel();
    await settle();
    expect(screen.getByText("Extraction job interrupted")).toBeInTheDocument();

    handle.corpusStart.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Start over" }));
    await settle();

    // A FRESH corpus job (new start-time prefix) — never an explicit start
    // over the empty chapterIds seed.
    expect(handle.corpusStart).toHaveBeenCalledTimes(1);
    expect(handle.corpusStart).toHaveBeenCalledWith(NOVEL);
    expect(handle.start).not.toHaveBeenCalled();
    expect(handle.status).toHaveBeenLastCalledWith(NOVEL, "job-corpus-2");
    expect(screen.getByText("1 of 4 chapters")).toBeInTheDocument(); // progress again
  });

  it("surfaces a failed corpus restart as an alert (visible, not silent)", async () => {
    handle.status.mockRejectedValue(
      new BulkExtractionApiError(404, "Bulk extraction job not found"),
    );
    handle.corpusStart.mockRejectedValue(
      new BulkExtractionApiError(409, "A bulk extraction job is already active for this novel"),
    );
    renderCorpusPanel();
    await settle();

    fireEvent.click(screen.getByRole("button", { name: "Start over" }));
    await settle();

    // ADR-043 §16.5: catalog copy, never the raw server detail.
    expect(screen.getByTestId("bulk-restart-error")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/could not be restarted/i);
    expect(screen.getByRole("alert")).not.toHaveTextContent(/already active/);
  });

  it("routes a transient first-poll failure's retry through the corpus restart, never an explicit start", async () => {
    // Transient (non-404) first poll: progress mode + surfaced error, and the
    // job never yielded a status (jobStatus null) → the retry affordance shows.
    handle.status
      .mockRejectedValueOnce(new BulkExtractionApiError(500, "analysis gateway unavailable"))
      .mockResolvedValue(statusView("running", fourChapters(), "job-corpus-2"));
    handle.corpusStart.mockResolvedValue(jobView("pending", "job-corpus-2"));
    renderCorpusPanel();
    await settle();
    expect(screen.getByRole("alert")).toHaveTextContent(/analysis gateway unavailable/i);

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await settle();

    // Invariant: corpus mode NEVER starts an explicit job over the empty
    // seed — the retry re-runs the CORPUS start and adopts the fresh job.
    expect(handle.start).not.toHaveBeenCalled();
    expect(handle.corpusStart).toHaveBeenCalledTimes(1);
    expect(handle.corpusStart).toHaveBeenCalledWith(NOVEL);
    expect(handle.status).toHaveBeenLastCalledWith(NOVEL, "job-corpus-2");
    expect(screen.getByText("1 of 4 chapters")).toBeInTheDocument(); // progress again
  });

  it("offers a retry after a failed corpus restart (no dead Starting… end state)", async () => {
    handle.status.mockRejectedValue(
      new BulkExtractionApiError(404, "Bulk extraction job not found"),
    );
    handle.corpusStart
      .mockRejectedValueOnce(
        new BulkExtractionApiError(409, "A bulk extraction job is already active for this novel"),
      )
      .mockResolvedValue(jobView("pending", "job-corpus-3"));
    renderCorpusPanel();
    await settle();

    fireEvent.click(screen.getByRole("button", { name: "Start over" }));
    await settle();
    expect(screen.getByTestId("bulk-restart-error")).toBeInTheDocument();

    // The restart failure must leave a retry affordance (the progress view's
    // "Starting…" is not a dead end) — and it re-runs the corpus start.
    handle.status.mockResolvedValue(statusView("running", fourChapters(), "job-corpus-3"));
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await settle();

    expect(handle.corpusStart).toHaveBeenCalledTimes(2);
    expect(handle.start).not.toHaveBeenCalled();
    expect(screen.getByText("1 of 4 chapters")).toBeInTheDocument(); // progress again
  });
});

// ---------------------------------------------------------------------------
// F3 corpus pass (plan Task 5): the dedup card in review mode + the minimal
// ADR-085 suggestions review. Copy ruling (T3 review, BINDING): the
// completion-time analysis ran over the PRE-APPLY roster — the card states
// that timing honestly, never "found N duplicates" as a static fact, and
// invites an on-demand re-check after applies.
// ---------------------------------------------------------------------------

describe("BulkExtractionPanel dedup card (F3 T5)", () => {
  /** One live suggestion pair served by the resolution endpoints. */
  function resolutionPair(): ResolutionAnalysisResponse {
    return {
      suggestions: [
        {
          suggestion_id: "sug-aaa",
          entry_a_id: "10000000-0000-0000-0000-000000000001",
          entry_b_id: "20000000-0000-0000-0000-000000000002",
          name_a: "Elena Varo",
          name_b: "Elena Maren",
          confidence: 0.82,
          band: "REVIEW",
          auto_merge_eligible: false,
          signals: [],
          adjudication_note: null,
        },
      ],
      stats: { review: 1, auto_eligible: 0, suppressed: 0 },
      cache_hit: false,
    };
  }

  /** Completed corpus job in review mode with the given dedup block. */
  async function renderCompletedCorpus(dedup: BulkDedupInfo | null) {
    handle.status.mockResolvedValue(
      statusView("completed", twoDoneChapters(), "job-corpus", null, dedup),
    );
    handle.results.mockResolvedValue(resultsView("completed", twoDoneChapters()));
    render(
      <QueryClientProvider client={createQueryClient()}>
        <BulkExtractionPanel
          novelId={NOVEL}
          chapterIds={[]}
          initialJobId="job-corpus"
          onClose={vi.fn()}
        />
      </QueryClientProvider>,
    );
    await settle();
  }

  beforeEach(() => {
    handle.resolutionList.mockResolvedValue(resolutionPair());
    handle.resolutionAnalyze.mockResolvedValue(resolutionPair());
    handle.resolutionEndorse.mockResolvedValue({
      survivor_id: "10000000-0000-0000-0000-000000000001",
      loser_id: "20000000-0000-0000-0000-000000000002",
      merged_fact_keys: [],
      repointed_relationships: 0,
      skipped_relationships: 0,
      conflicts: [],
    });
  });

  it("hides the dedup card entirely for a job without a dedup block", async () => {
    await renderCompletedCorpus(null);
    expect(screen.queryByText(/possible duplicates/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Duplicate check unavailable/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Review duplicates" })).not.toBeInTheDocument();
  });

  it("renders the muted unavailable variant when the automatic analysis failed", async () => {
    await renderCompletedCorpus({ analyzed: false, suggestion_count: null });
    expect(screen.getByText(/Duplicate check unavailable/)).toBeInTheDocument();
    // Non-blocking: no review affordance is offered for a check that never ran.
    expect(screen.queryByRole("button", { name: "Review duplicates" })).not.toBeInTheDocument();
  });

  it("states the pre-apply timing honestly and lazily opens the suggestions list", async () => {
    await renderCompletedCorpus({ analyzed: true, suggestion_count: 7 });

    // Honest copy: the count is flagged at completion, NOT a static fact.
    const line = screen.getByText(/7 possible duplicates/);
    expect(line).toHaveTextContent("before items were applied");

    // Lazy: the list is NOT fetched until the user opens the review.
    expect(handle.resolutionList).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Review duplicates" }));
    await settle();

    expect(handle.resolutionList).toHaveBeenCalledWith(NOVEL, expect.anything());
    expect(screen.getByText("Elena Varo ↔ Elena Maren")).toBeInTheDocument();
  });

  it("uses the clean copy for a zero count instead of '0 possible duplicates'", async () => {
    await renderCompletedCorpus({ analyzed: true, suggestion_count: 0 });
    expect(screen.getByText(/found no duplicates/)).toHaveTextContent("before items were applied");
    expect(screen.queryByText(/0 possible duplicates/)).not.toBeInTheDocument();
    // Re-check stays available: applies change the KB after the pass.
    expect(screen.getByRole("button", { name: "Re-check duplicates" })).toBeInTheDocument();
  });

  it("re-check runs an on-demand analysis and swaps the card to the fresh count", async () => {
    await renderCompletedCorpus({ analyzed: true, suggestion_count: 2 });

    fireEvent.click(screen.getByRole("button", { name: "Re-check duplicates" }));
    await settle();

    expect(handle.resolutionAnalyze).toHaveBeenCalledWith(NOVEL);
    // Fresh line replaces the stale registry count (1 live pair in the fixture).
    expect(
      screen.getByText(/Fresh check on the current Knowledge Base: 1 possible duplicates/),
    ).toBeInTheDocument();
    // The fresh result opens the list with the authoritative data.
    expect(screen.getByText("Elena Varo ↔ Elena Maren")).toBeInTheDocument();
  });
});
