/**
 * ai-mutation-adapter tests — shared mutation-adapter utilities.
 *
 * These factories build the callbacks/return used by every useAIOperation-based
 * mutation hook. The existing hook tests mock useAIOperation, so the *bodies*
 * of these callbacks (abort/error-mapper/onSuccess/onError) are never invoked.
 * This file exercises them directly.
 *
 * Covers:
 *  - createAbortAwareErrorMapper: AbortError (DOMException + Error) vs fallback
 *  - createOnSuccessCallback: resolves the pending promise
 *  - createOnErrorCallback: rejects with Error(userMessage)
 *  - buildMutationReturn: isPending / error / isSuccess ternaries
 *  - useAbortCallback / useMutateAsyncFactory (hooks, via renderHook)
 */

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  buildMutationReturn,
  createAbortAwareErrorMapper,
  createOnErrorCallback,
  createOnSuccessCallback,
  useAbortCallback,
  useMutateAsyncFactory,
} from "@/lib/hooks/ai-mutation-adapter";
import type { UseAIOperationReturn } from "@/lib/hooks/use-ai-operation";

function makeAiOp<T>(overrides: Partial<UseAIOperationReturn<T>> = {}): UseAIOperationReturn<T> {
  return {
    state: { status: "idle", result: null, error: null, attemptCount: 0 } as never,
    start: vi.fn(),
    cancel: vi.fn(),
    retry: vi.fn(),
    reset: vi.fn(),
    notifyData: vi.fn(),
    isIdle: true,
    isLoading: false,
    isStreaming: false,
    isComplete: false,
    isError: false,
    isConnectionLost: false,
    ...overrides,
  } as UseAIOperationReturn<T>;
}

describe("createAbortAwareErrorMapper", () => {
  it("rejects and returns null for a DOMException AbortError", () => {
    const resolve = vi.fn();
    const reject = vi.fn();
    const resolveRef = { current: resolve };
    const rejectRef = { current: reject };
    const fallback = vi.fn();
    const mapper = createAbortAwareErrorMapper(resolveRef, rejectRef, fallback);

    const result = mapper(new DOMException("aborted", "AbortError"));

    expect(result).toBeNull();
    expect(reject).toHaveBeenCalledWith(expect.any(DOMException));
    expect(resolveRef.current).toBeNull();
    expect(rejectRef.current).toBeNull();
    expect(fallback).not.toHaveBeenCalled();
  });

  it("rejects and returns null for an Error named AbortError", () => {
    const resolve = vi.fn();
    const reject = vi.fn();
    const resolveRef = { current: resolve };
    const rejectRef = { current: reject };
    const fallback = vi.fn();
    const err = new Error("aborted");
    err.name = "AbortError";
    const mapper = createAbortAwareErrorMapper(resolveRef, rejectRef, fallback);

    expect(mapper(err)).toBeNull();
    expect(reject).toHaveBeenCalledWith(err);
  });

  it("delegates non-abort errors to the fallback mapper", () => {
    const resolveRef = { current: vi.fn() };
    const rejectRef = { current: vi.fn() };
    const mapped = { userMessage: "boom" } as never;
    const fallback = vi.fn().mockReturnValue(mapped);
    const mapper = createAbortAwareErrorMapper(resolveRef, rejectRef, fallback);

    const err = new Error("boom");
    expect(mapper(err)).toBe(mapped);
    expect(fallback).toHaveBeenCalledWith(err);
    expect(rejectRef.current).not.toHaveBeenCalled();
  });
});

describe("createOnSuccessCallback", () => {
  it("resolves the pending promise and clears the refs", () => {
    const resolve = vi.fn();
    const reject = vi.fn();
    const resolveRef = { current: resolve };
    const rejectRef = { current: reject };
    const onSuccess = createOnSuccessCallback(resolveRef, rejectRef);

    onSuccess("data" as never);

    expect(resolve).toHaveBeenCalledWith("data");
    expect(resolveRef.current).toBeNull();
    expect(rejectRef.current).toBeNull();
  });

  it("is a no-op when no promise is pending", () => {
    const resolveRef = { current: null };
    const rejectRef = { current: null };
    createOnSuccessCallback(resolveRef, rejectRef)("data" as never);
    // No throw, refs remain null.
    expect(resolveRef.current).toBeNull();
  });
});

describe("createOnErrorCallback", () => {
  it("rejects with an Error built from userMessage", () => {
    const resolve = vi.fn();
    const reject = vi.fn();
    const resolveRef = { current: resolve };
    const rejectRef = { current: reject };
    const onError = createOnErrorCallback(resolveRef, rejectRef);

    onError({ userMessage: "something failed" } as never);

    expect(reject).toHaveBeenCalledWith(expect.any(Error));
    expect(reject.mock.calls[0][0]).toBeInstanceOf(Error);
    expect((reject.mock.calls[0][0] as Error).message).toBe("something failed");
    expect(resolveRef.current).toBeNull();
  });
});

describe("buildMutationReturn", () => {
  it("maps a complete, error-free operation", () => {
    const aiOp = makeAiOp({
      state: { status: "complete", result: "ok" as never, error: null, attemptCount: 1 },
      isComplete: true,
      isLoading: false,
      isStreaming: false,
    });

    const ret = buildMutationReturn(aiOp, vi.fn(), vi.fn(), vi.fn(), { id: "x" });

    expect(ret.isSuccess).toBe(true);
    expect(ret.isPending).toBe(false);
    expect(ret.error).toBeNull();
    expect(ret.data).toBe("ok");
    expect(ret.variables).toEqual({ id: "x" });
  });

  it("maps an error operation", () => {
    const aiOp = makeAiOp({
      state: {
        status: "error",
        result: null,
        error: { userMessage: "failed" } as never,
        attemptCount: 1,
      },
      isError: true,
    });

    const ret = buildMutationReturn(aiOp, vi.fn(), vi.fn(), vi.fn(), null);

    expect(ret.isSuccess).toBe(false);
    expect(ret.error).toBeInstanceOf(Error);
    expect(ret.error?.message).toBe("failed");
  });

  it("reports isPending while loading or streaming", () => {
    const loading = makeAiOp({ isLoading: true, isStreaming: false });
    const streaming = makeAiOp({ isLoading: false, isStreaming: true });
    const idle = makeAiOp({ isLoading: false, isStreaming: false });

    expect(buildMutationReturn(loading, vi.fn(), vi.fn(), vi.fn(), null).isPending).toBe(true);
    expect(buildMutationReturn(streaming, vi.fn(), vi.fn(), vi.fn(), null).isPending).toBe(true);
    expect(buildMutationReturn(idle, vi.fn(), vi.fn(), vi.fn(), null).isPending).toBe(false);
  });

  it("surfaces the primitive's start/cancel/retry/reset", () => {
    const aiOp = makeAiOp();
    const ret = buildMutationReturn(aiOp, vi.fn(), vi.fn(), vi.fn(), null);

    ret.start();
    ret.cancel();
    ret.retry();
    ret.reset();
    ret.notifyData();

    expect(aiOp.start).toHaveBeenCalled();
    expect(aiOp.cancel).toHaveBeenCalled();
    expect(aiOp.retry).toHaveBeenCalled();
    expect(aiOp.reset).toHaveBeenCalled();
    expect(aiOp.notifyData).toHaveBeenCalled();
  });
});

describe("useAbortCallback", () => {
  it("rejects the pending promise, clears refs and cancels", () => {
    const resolveMock = vi.fn();
    const rejectMock = vi.fn();
    const resolveRef = { current: resolveMock as ((v: unknown) => void) | null };
    const rejectRef = { current: rejectMock as ((r: unknown) => void) | null };
    const aiOp = makeAiOp();

    const { result } = renderHook(() => useAbortCallback(resolveRef, rejectRef, aiOp));

    act(() => {
      result.current();
    });

    // Capture mocks *before* the callback clears the refs.
    expect(rejectMock).toHaveBeenCalledWith(expect.any(DOMException));
    expect(resolveRef.current).toBeNull();
    expect(rejectRef.current).toBeNull();
    expect(aiOp.cancel).toHaveBeenCalled();
  });
});

describe("useMutateAsyncFactory", () => {
  it("stages args, stores resolvers, and starts the operation", () => {
    const argsRef = { current: null as unknown };
    const resolveRef = { current: null as ((v: unknown) => void) | null };
    const rejectRef = { current: null as ((r: unknown) => void) | null };
    const aiOp = makeAiOp();

    const { result } = renderHook(() =>
      useMutateAsyncFactory(argsRef, resolveRef, rejectRef, aiOp),
    );

    let resolved: unknown;
    result.current("payload").then((v) => {
      resolved = v;
    });

    expect(argsRef.current).toBe("payload");
    expect(resolveRef.current).toBeTypeOf("function");
    expect(rejectRef.current).toBeTypeOf("function");
    expect(aiOp.start).toHaveBeenCalled();

    // Resolve the staged promise.
    resolveRef.current?.("done");
    return Promise.resolve().then(() => expect(resolved).toBe("done"));
  });
});
