/**
 * Shared test helpers for useAIOperation tests.
 *
 * Provides:
 * - createMockExecute: controlled promise-based execute mock
 * - createAbortError: DOMException-like AbortError factory
 */

import { vi } from "vitest";

/** Create a mock execute function that can be controlled. */
export function createMockExecute<T = string>(resolveValue?: T) {
  let resolveFn: (value: T) => void;
  let rejectFn: (error: unknown) => void;

  const promise = new Promise<T>((resolve, reject) => {
    resolveFn = resolve;
    rejectFn = reject;
  });

  const mockFn = vi.fn((_signal: AbortSignal) => promise);

  return {
    execute: mockFn,
    resolve: (value: T) => resolveFn!(value ?? resolveValue!),
    reject: (error: unknown) => rejectFn!(error),
    promise,
  };
}

/** Create an AbortError (DOMException-like). */
export function createAbortError(): DOMException {
  return new DOMException("The operation was aborted.", "AbortError");
}
