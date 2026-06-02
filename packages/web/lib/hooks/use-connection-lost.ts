"use client";

import { useCallback, useRef, useState } from "react";

/**
 * Reusable hook for detecting SSE/stream disconnections in AI features.
 *
 * Usage:
 *   const { isConnectionLost, retry, clearError } = useConnectionLost({
 *     onRetry: handleRetry,
 *   });
 *
 * Call `setConnectionLost(true)` when the stream drops (e.g. in an SSE
 * `onerror` handler or when the response promise rejects).
 */
interface UseConnectionLostOptions {
  /** Callback invoked when the user clicks "Retry". */
  onRetry: () => void;
}

interface UseConnectionLostReturn {
  /** Whether the connection is currently lost. */
  isConnectionLost: boolean;
  /** Mark the connection as lost. */
  markConnectionLost: () => void;
  /** Clear the lost state (e.g. after a successful reconnect). */
  clearError: () => void;
  /** Trigger retry: clears state and calls onRetry. */
  retry: () => void;
}

export function useConnectionLost({ onRetry }: UseConnectionLostOptions): UseConnectionLostReturn {
  const [isConnectionLost, setIsConnectionLost] = useState(false);
  const onRetryRef = useRef(onRetry);
  onRetryRef.current = onRetry;

  const markConnectionLost = useCallback(() => {
    setIsConnectionLost(true);
  }, []);

  const clearError = useCallback(() => {
    setIsConnectionLost(false);
  }, []);

  const retry = useCallback(() => {
    setIsConnectionLost(false);
    onRetryRef.current();
  }, []);

  return { isConnectionLost, markConnectionLost, clearError, retry };
}
