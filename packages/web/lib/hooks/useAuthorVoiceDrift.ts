"use client";

/**
 * useAuthorVoiceDrift — SSE streaming hook for Author Voice Drift
 * (ANAL-009 Phase 2B).
 *
 * Wraps {@link useAIOperation} with the author-voice-drift streaming logic, the
 * same way {@link useCharacterVoiceDrift} wraps `streamVoiceDrift`. The
 * SSE → Promise bridge lives in {@link ./author-voice-drift-executor}
 * (RULE-04 extraction).
 *
 * Author voice is ONE narrator per novel, so the hook surfaces a SINGLE
 * `result` (not a per-character array like Phase 1) OR a SINGLE graceful
 * `noProfile` skip — never both.
 *
 * Author-voice-drift is **novel-scoped**: `run(novelId, chapterIds?)`
 * analyses the whole novel; an optional `chapter_ids` filter may be staged.
 * Enforces ADR-043: no manual AbortController — the abort signal comes from
 * `useAIOperation`.
 *
 * @module useAuthorVoiceDrift
 */

import { useCallback, useRef, useState } from "react";
import type { AuthorVoiceDriftRequest } from "@/lib/api/author-voice-drift-stream";
import {
  type AuthorVoiceDriftRunResult,
  createAuthorVoiceDriftExecute,
} from "@/lib/hooks/author-voice-drift-executor";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

/**
 * @returns lifecycle (state/flags/cancel/retry/reset), `run`, the singular
 *          `result`, the graceful `noProfile` skip, and `progress`.
 */
export function useAuthorVoiceDrift() {
  // Staged before each start() so execute() reads the current values via refs.
  const novelIdRef = useRef<string | null>(null);
  const bodyRef = useRef<AuthorVoiceDriftRequest>({ chapter_ids: null });
  const [progress, setProgress] = useState<string | null>(null);

  const {
    state,
    start,
    cancel,
    retry,
    reset,
    notifyData,
    isIdle,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  } = useAIOperation<AuthorVoiceDriftRunResult>({
    execute: createAuthorVoiceDriftExecute({
      getNovelId: () => novelIdRef.current,
      getBody: () => bodyRef.current,
      setProgress,
      // Deferred: notifyData is returned BY useAIOperation, so it is not yet
      // bound when this config object is constructed. The lambda resolves it
      // at execute-time (after useAIOperation has returned).
      notifyData: () => notifyData(),
    }),
    connectionLossTimeout: 15_000,
  });

  /** Stage the novel + optional chapter filter and start the drift analysis. */
  const run = useCallback(
    (novelId: string, chapterIds?: string[] | null) => {
      novelIdRef.current = novelId;
      bodyRef.current = chapterIds ? { chapter_ids: chapterIds } : { chapter_ids: null };
      setProgress(null);
      start();
    },
    [start],
  );

  /** Reset to idle, clearing result, no-profile, error, and progress. */
  const handleReset = useCallback(() => {
    setProgress(null);
    reset();
  }, [reset]);

  const runResult = state.result;

  return {
    state,
    result: runResult?.result ?? null,
    noProfile: runResult?.noProfile ?? null,
    progress,
    error: state.error,
    run,
    cancel,
    retry,
    reset: handleReset,
    isIdle,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  };
}
