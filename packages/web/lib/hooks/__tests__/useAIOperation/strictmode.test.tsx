/**
 * StrictMode double-mount tests for useAIOperation.
 *
 * Reproduces F9-3: Next dev (app router) runs mount effects as
 * setup → cleanup → setup. Auto-check surfaces (ConsistencyCheckPanel et al.)
 * fire start() on every setup and cancel() on every cleanup. The cleanup's
 * cancel() used to bump operationIdRef INSIDE a setState updater, which
 * StrictMode double-invokes (updaters must be pure) — invalidating the
 * operation the LATER setup had just started, so every result was dropped by
 * the stale guard and the surface latched "Connection lost" (dev only).
 *
 * The invariant under test: a cleanup's cancel() may only invalidate
 * operations started BEFORE it; an operation started by a later setup must
 * still land.
 */

import { act, render, renderHook, screen } from "@testing-library/react";
import { StrictMode, useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { createMockExecute } from "./setup";

/**
 * Harness mirroring ConsistencyCheckPanel's auto-check wiring:
 * mount effect starts the op (fires on every setup), a dedicated cleanup
 * effect cancels it (fires on every cleanup). No started-ref guard —
 * exactly like the panel.
 */
function AutoCheckHarness({ execute }: { execute: (signal: AbortSignal) => Promise<string> }) {
  const op = useAIOperation<string>({
    execute,
    connectionLossTimeout: 0,
  });

  // Auto-trigger on mount (fires on every StrictMode setup)
  // biome-ignore lint/correctness/useExhaustiveDependencies: mount-only
  useEffect(() => {
    if (op.isIdle) op.start();
  }, []);

  // Cleanup on unmount (fires on every StrictMode cleanup)
  // biome-ignore lint/correctness/useExhaustiveDependencies: mount-only
  useEffect(() => {
    return () => op.cancel();
  }, []);

  return (
    <div data-testid="auto-check-state" data-status={op.state.status}>
      {op.state.result}
    </div>
  );
}

describe("useAIOperation — StrictMode double-mount", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // F9-3 regression: under StrictMode the cleanup's cancel() double-fired the
  // op-id bump inside a setState updater, invalidating the second setup's
  // operation — the response resolved 200 but the stale guard dropped it and
  // the surface never left "loading" (→ "Connection lost" after 15s).
  // The later setup's result must land.
  it("lands the result of the operation started by the second setup", async () => {
    let resolveOp: (value: string) => void = () => {};
    const execute = vi.fn(
      (_signal: AbortSignal) =>
        new Promise<string>((resolve) => {
          resolveOp = resolve;
        }),
    );

    render(
      <StrictMode>
        <AutoCheckHarness execute={execute} />
      </StrictMode>,
    );

    // Flush the queued invokeExecute microtasks (StrictMode setups queue one each)
    await act(async () => {
      vi.advanceTimersByTime(0);
    });
    expect(execute).toHaveBeenCalled();

    await act(async () => {
      resolveOp("check-result");
    });

    expect(screen.getByTestId("auto-check-state").dataset.status).toBe("complete");
    expect(screen.getByTestId("auto-check-state").textContent).toBe("check-result");
  });

  // Invariant guard: the fix must not weaken the stale-guard semantics —
  // an explicit cancel() still invalidates an operation started before it.
  it("still drops the result of an operation cancelled before resolution", async () => {
    const mock = createMockExecute("stale-result");
    const { result } = renderHook(
      () => useAIOperation<string>({ execute: mock.execute, connectionLossTimeout: 0 }),
      { wrapper: StrictMode },
    );

    act(() => {
      result.current.start();
    });
    act(() => {
      result.current.cancel();
    });
    expect(result.current.state.status).toBe("idle");

    await act(async () => {
      mock.resolve("stale-result");
    });

    expect(result.current.state.status).toBe("idle");
    expect(result.current.state.result).toBeNull();
  });
});
