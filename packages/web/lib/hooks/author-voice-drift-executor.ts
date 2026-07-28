"use client";

/**
 * Author-voice-drift SSE → Promise executor (ANAL-009 Phase 2B).
 *
 * Extracted from {@link ./useAuthorVoiceDrift} per RULE-04 (hook file-size
 * limit). Owns the SINGLE responsibility of bridging the callback-based
 * {@link streamAuthorVoiceDrift} stream to the `execute(signal) => Promise<T>`
 * contract of {@link useAIOperation} (ADR-043):
 *  - `onProgress` refreshes the streaming liveness timer (`notifyData`) AND
 *    surfaces the latest pipeline status message via the hook's `progress`.
 *  - `onResult` captures the SINGLE narrator result (author voice is one
 *    narrator per novel — not a per-character list like Phase 1).
 *  - `onNoProfile` captures the SINGLE graceful RULE-11 skip.
 *  - `onComplete` resolves with `{ result, noProfile }`; `onError` rejects;
 *    abort → `AbortError` rejection (swallowed on cancel by useAIOperation).
 *
 * Mirrors the precedent of {@link ./ai-operation-execute.ts} (a focused
 * executor module kept separate from its owning hook).
 *
 * @module author-voice-drift-executor
 */

import {
  type AuthorVoiceDriftNoProfile,
  type AuthorVoiceDriftRequest,
  type AuthorVoiceDriftResult,
  streamAuthorVoiceDrift,
} from "@/lib/api/author-voice-drift-stream";

/** The composite resolved by the executor — singular result OR graceful skip. */
export interface AuthorVoiceDriftRunResult {
  result: AuthorVoiceDriftResult | null;
  noProfile: AuthorVoiceDriftNoProfile | null;
}

/** Read-only accessors the hook supplies from its staged refs / state. */
interface ExecutorDeps {
  /** Reads the staged novel id (null when no run has been staged). */
  getNovelId: () => string | null;
  /** Reads the staged request body (the optional chapter filter). */
  getBody: () => AuthorVoiceDriftRequest;
  /** Replaces the latest progress message (null clears it). */
  setProgress: (message: string | null) => void;
  /** Refreshes the useAIOperation streaming-liveness watchdog. */
  notifyData: () => void;
}

/** The `execute` callback shape expected by {@link useAIOperation}. */
export type AuthorVoiceDriftExecute = (signal: AbortSignal) => Promise<AuthorVoiceDriftRunResult>;

/**
 * Build the `execute(signal)` callback for {@link useAIOperation} that streams
 * one author-voice-drift analysis and resolves with the captured result OR the
 * graceful no-profile skip. The hook supplies the staged novel id / body via
 * the read-only accessors so each run reads the values staged at `start()`.
 */
export function createAuthorVoiceDriftExecute(deps: ExecutorDeps): AuthorVoiceDriftExecute {
  return (signal) =>
    new Promise<AuthorVoiceDriftRunResult>((resolve, reject) => {
      const id = deps.getNovelId();
      if (!id) {
        reject(new Error("No novel id provided for author-voice-drift analysis"));
        return;
      }

      let settled = false;
      let capturedResult: AuthorVoiceDriftResult | null = null;
      let capturedNoProfile: AuthorVoiceDriftNoProfile | null = null;

      const onAbort = () => {
        if (!settled) {
          settled = true;
          reject(new DOMException("Aborted", "AbortError"));
        }
      };
      signal.addEventListener("abort", onAbort, { once: true });

      streamAuthorVoiceDrift(
        id,
        deps.getBody(),
        {
          onProgress: (message) => {
            deps.notifyData();
            deps.setProgress(message);
          },
          onResult: (result) => {
            deps.notifyData();
            // Author voice is ONE narrator per novel — capture the single
            // result event (the last one wins, defensively).
            capturedResult = result;
          },
          onNoProfile: (noProfile) => {
            deps.notifyData();
            capturedNoProfile = noProfile;
          },
          onComplete: () => {
            if (!settled) {
              settled = true;
              signal.removeEventListener("abort", onAbort);
              resolve({ result: capturedResult, noProfile: capturedNoProfile });
            }
          },
          onError: (err) => {
            if (!settled) {
              settled = true;
              signal.removeEventListener("abort", onAbort);
              reject(err);
            }
          },
        },
        signal,
      );
    });
}
