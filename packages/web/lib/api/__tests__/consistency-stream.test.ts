/**
 * consistency-stream client unit tests — event discrimination.
 *
 * The SSE transport (`./streaming`) is mocked; each test captures the
 * `connectSSE` options and drives `onChunk` with typed events to verify the
 * client translates the discriminated event stream into the correct handlers
 * (stage / progressive issue / result / error) and dedupes the terminal
 * completion (result event + transport `[DONE]` sentinel).
 *
 * @module consistency-stream.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/streaming", () => ({
  connectSSE: vi.fn(),
}));

import type { ConsistencyIssue } from "@/lib/api/analysis";
import {
  type ConsistencyCheckRequest,
  type ConsistencyResultPayload,
  type ConsistencyStreamEvent,
  streamConsistencyCheck,
} from "@/lib/api/consistency-stream";
import { connectSSE, type SSEOptions, SSEStreamError } from "@/lib/api/streaming";

const mockedConnectSSE = vi.mocked(connectSSE);

interface Captured {
  options: SSEOptions<ConsistencyStreamEvent>;
  onChunk: (event: ConsistencyStreamEvent) => void;
}

function capture(): Captured {
  expect(mockedConnectSSE).toHaveBeenCalled();
  const options = mockedConnectSSE.mock.calls.at(-1)?.[0] as
    | SSEOptions<ConsistencyStreamEvent>
    | undefined;
  expect(options).toBeDefined();
  return { options: options!, onChunk: options!.onChunk };
}

const sampleIssue: ConsistencyIssue = {
  check_type: "character",
  severity: "error",
  description: "Eye colour mismatch for character Anna.",
  locations: ["Chapter 1", "Chapter 5"],
  conflicting_facts: ["Anna has blue eyes in Chapter 1", "Anna has green eyes in Chapter 5"],
  suggestion: "Standardise eye colour to blue across all chapters.",
  confidence: 0.92,
};

const sampleResult: ConsistencyResultPayload = {
  novel_id: "novel-1",
  chapter_ids: ["ch-1", "ch-2", "ch-3"],
  check_types: ["character", "timeline", "world", "plot"],
  issues: [sampleIssue],
  error_count: 1,
  warning_count: 2,
  info_count: 0,
  total_issues: 3,
  overall_assessment: "Mostly consistent with minor issues.",
  analyzed_at: "2026-06-30T12:00:00Z",
};

const defaultRequest: ConsistencyCheckRequest = {
  chapter_ids: ["ch-1", "ch-2", "ch-3"],
  check_types: ["character", "timeline", "world", "plot"],
  include_kb: true,
};

describe("streamConsistencyCheck", () => {
  beforeEach(() => {
    mockedConnectSSE.mockClear();
  });

  it("POSTs to the consistency check stream endpoint with the request body", async () => {
    await streamConsistencyCheck("novel-1", defaultRequest, {
      onStage: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
    });

    const { options } = capture();
    expect(options.url).toBe("/consistency/check/stream?novel_id=novel-1");
    expect(options.method).toBe("POST");
    expect(options.body).toEqual(defaultRequest);
  });

  it("calls onStage for extracting_facts stage events", async () => {
    const onStage = vi.fn();
    await streamConsistencyCheck("novel-1", defaultRequest, {
      onStage,
      onComplete: vi.fn(),
      onError: vi.fn(),
    });

    capture().onChunk({
      type: "stage",
      stage: "extracting_facts",
      status: "start",
      progress: 0,
      message: "Extracting facts from chapters...",
      facts_extracted: null,
      issues_found: null,
    });

    expect(onStage).toHaveBeenCalledOnce();
    expect(onStage).toHaveBeenCalledWith(
      "extracting_facts",
      "start",
      0,
      "Extracting facts from chapters...",
      null,
      null,
    );
  });

  it("calls onStage for checking_consistency stage progress", async () => {
    const onStage = vi.fn();
    await streamConsistencyCheck("novel-1", defaultRequest, {
      onStage,
      onComplete: vi.fn(),
      onError: vi.fn(),
    });

    capture().onChunk({
      type: "stage",
      stage: "checking_consistency",
      status: "progress",
      progress: 0.5,
      message: "Checking character consistency...",
      facts_extracted: 42,
      issues_found: 3,
    });

    expect(onStage).toHaveBeenCalledOnce();
    expect(onStage).toHaveBeenCalledWith(
      "checking_consistency",
      "progress",
      0.5,
      "Checking character consistency...",
      42,
      3,
    );
  });

  it("calls onIssue for progressive issues during checking_consistency", async () => {
    const onIssue = vi.fn();
    await streamConsistencyCheck("novel-1", defaultRequest, {
      onIssue,
      onStage: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
    });

    capture().onChunk({
      type: "stage",
      stage: "checking_consistency",
      status: "issue",
      progress: 0.3,
      message: "Found potential inconsistency...",
      issue: sampleIssue,
      facts_extracted: null,
      issues_found: 1,
    });

    expect(onIssue).toHaveBeenCalledOnce();
    expect(onIssue).toHaveBeenCalledWith(sampleIssue);
  });

  it("calls onComplete with the final result payload", async () => {
    const onComplete = vi.fn();
    await streamConsistencyCheck("novel-1", defaultRequest, {
      onStage: vi.fn(),
      onComplete,
      onError: vi.fn(),
    });

    capture().onChunk({
      type: "result",
      novel_id: "novel-1",
      chapter_ids: ["ch-1", "ch-2", "ch-3"],
      check_types: ["character", "timeline", "world", "plot"],
      issues: [sampleIssue],
      error_count: 1,
      warning_count: 2,
      info_count: 0,
      total_issues: 3,
      overall_assessment: "Mostly consistent with minor issues.",
      analyzed_at: "2026-06-30T12:00:00Z",
    });

    expect(onComplete).toHaveBeenCalledOnce();
    expect(onComplete).toHaveBeenCalledWith(sampleResult);
  });

  it("surfaces a terminal error event via onError", async () => {
    const onError = vi.fn();
    await streamConsistencyCheck("novel-1", defaultRequest, {
      onStage: vi.fn(),
      onComplete: vi.fn(),
      onError,
    });

    capture().onChunk({ type: "error", error: "Consistency check failed." });

    expect(onError).toHaveBeenCalledOnce();
    expect(onError.mock.calls[0]?.[0]).toBeInstanceOf(Error);
    expect((onError.mock.calls[0]?.[0] as Error).message).toBe("Consistency check failed.");
  });

  it("does not fire onComplete after an error event", async () => {
    const onComplete = vi.fn();
    const onError = vi.fn();
    await streamConsistencyCheck("novel-1", defaultRequest, {
      onStage: vi.fn(),
      onComplete,
      onError,
    });

    const onChunk = capture().onChunk;
    onChunk({ type: "error", error: "Consistency check failed." });
    // A subsequent result event must not fire onComplete after the error path ran.
    onChunk({ type: "result", issues: [] });

    expect(onError).toHaveBeenCalledOnce();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("completes once on the result event and does not double-fire on the [DONE] sentinel", async () => {
    const onComplete = vi.fn();
    await streamConsistencyCheck("novel-1", defaultRequest, {
      onStage: vi.fn(),
      onComplete,
      onError: vi.fn(),
    });

    const { options, onChunk } = capture();
    onChunk({ type: "result", novel_id: "novel-1", issues: [] });
    // The transport invokes its own onComplete when it sees `data: [DONE]`.
    options.onComplete?.(undefined);

    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("handles abort signal", async () => {
    const abortController = new AbortController();
    const onError = vi.fn();

    await streamConsistencyCheck(
      "novel-1",
      defaultRequest,
      {
        onStage: vi.fn(),
        onComplete: vi.fn(),
        onError,
      },
      abortController.signal,
    );

    const { options } = capture();
    expect(options.signal).toBe(abortController.signal);
  });

  it("calls handlers.onComplete when transport completes without a result event", async () => {
    const onComplete = vi.fn();

    await streamConsistencyCheck("novel-1", defaultRequest, {
      onStage: vi.fn(),
      onComplete,
      onError: vi.fn(),
    });

    const { options } = capture();
    // Transport onComplete is called before any result event
    options.onComplete?.(undefined);

    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("does not forward errors once the stream has completed", async () => {
    const onError = vi.fn();
    const onComplete = vi.fn();

    await streamConsistencyCheck("novel-1", defaultRequest, {
      onStage: vi.fn(),
      onComplete,
      onError,
    });

    const { options, onChunk } = capture();
    // First fire a result event (completes the stream)
    onChunk({ type: "result", novel_id: "novel-1", issues: [] });
    // Then transport reports an error - should be suppressed
    options.onError?.(new SSEStreamError("late transport error", "stream"));

    expect(onComplete).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });

  it("does not fail when onStage callback is not provided", async () => {
    await streamConsistencyCheck("novel-1", defaultRequest, {
      onComplete: vi.fn(),
      onError: vi.fn(),
    });

    const { onChunk } = capture();
    // Should not throw even without onStage
    onChunk({
      type: "stage",
      stage: "extracting_facts",
      status: "start",
      progress: 0,
      message: "",
    });
  });

  it("does not fail when onError callback is not provided", async () => {
    await streamConsistencyCheck("novel-1", defaultRequest, {
      onStage: vi.fn(),
      onComplete: vi.fn(),
    });

    const { options } = capture();
    // Should not throw even without onError
    options.onError?.(new SSEStreamError("transport error", "stream"));
  });
});
