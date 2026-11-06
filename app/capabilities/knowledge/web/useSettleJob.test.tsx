// @vitest-environment jsdom
/**
 * The settle beat the knowledge panels share: the row turning done or
 * failed is the moment the queue it feeds exists (or provably will not),
 * so that is when the queue refetches. Between the enqueue and that answer
 * the trigger stays closed (one job at a time); a dead poll reopens it.
 */
import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { queryClient } from "@shell/lib/query";

import { useSettleJob } from "./useSettleJob";

afterEach(() => {
  vi.restoreAllMocks();
});

function settledKey(queue: "suggestions" | "findings") {
  return ["knowledge", queue, "novel"];
}

describe("useSettleJob", () => {
  it("refetches the queue exactly when the row settles, with the queue's own key", () => {
    const invalidate = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined as never);
    const { result, rerender } = renderHook(
      ({ status }: { status: string | undefined }) =>
        useSettleJob({
          jobId: "job",
          status,
          pollError: false,
          enqueuePending: false,
          novelId: "novel",
          queue: "suggestions",
        }),
      { initialProps: { status: "queued" as string | undefined } },
    );

    expect(result.current.settled).toBe(false);
    expect(invalidate).not.toHaveBeenCalled();

    rerender({ status: "running" });
    expect(result.current.settled).toBe(false);
    expect(invalidate).not.toHaveBeenCalled();

    rerender({ status: "done" });
    expect(result.current.settled).toBe(true);
    expect(invalidate).toHaveBeenCalledTimes(1);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: settledKey("suggestions") });
  });

  it("settles a failed row too, on the findings key", () => {
    const invalidate = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined as never);
    const { result } = renderHook(() =>
      useSettleJob({
        jobId: "job",
        status: "failed",
        pollError: false,
        enqueuePending: false,
        novelId: "novel",
        queue: "findings",
      }),
    );

    expect(result.current.settled).toBe(true);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: settledKey("findings") });
  });

  it("reads a dead poll as an error, never as outstanding work", () => {
    const { result, rerender } = renderHook(
      ({ pollError }: { pollError: boolean }) =>
        useSettleJob({
          jobId: "job",
          status: "running",
          pollError,
          enqueuePending: false,
          novelId: "novel",
          queue: "findings",
        }),
      { initialProps: { pollError: false } },
    );

    // Outstanding and unanswered: the trigger stays closed.
    expect(result.current.pollFailed).toBe(false);
    expect(result.current.busy).toBe(true);

    // The same row, unanswered: the trigger reopens for the retry.
    rerender({ pollError: true });
    expect(result.current.pollFailed).toBe(true);
    expect(result.current.busy).toBe(false);
  });

  it("holds the trigger while the enqueue is in flight and frees it on refusal", () => {
    const { result, rerender } = renderHook(
      ({ enqueuePending }: { enqueuePending: boolean }) =>
        useSettleJob({
          jobId: null,
          status: undefined,
          pollError: false,
          enqueuePending,
          novelId: "novel",
          queue: "suggestions",
        }),
      { initialProps: { enqueuePending: true } },
    );

    expect(result.current.busy).toBe(true);

    rerender({ enqueuePending: false });
    expect(result.current.pollFailed).toBe(false);
    expect(result.current.busy).toBe(false);
  });

  it("frees the trigger when the row settles", () => {
    vi.spyOn(queryClient, "invalidateQueries").mockResolvedValue(undefined as never);
    const { result, rerender } = renderHook(
      ({ status }: { status: string | undefined }) =>
        useSettleJob({
          jobId: "job",
          status,
          pollError: false,
          enqueuePending: false,
          novelId: "novel",
          queue: "suggestions",
        }),
      { initialProps: { status: "running" as string | undefined } },
    );

    expect(result.current.busy).toBe(true);
    rerender({ status: "done" });
    expect(result.current.busy).toBe(false);
  });
});
