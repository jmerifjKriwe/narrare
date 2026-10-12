/**
 * Continue-writing SSE → Promise bridge.
 *
 * Bridges the callback-based SSE transport ({@link streamExtend}) to
 * {@link useAIOperation}'s `execute(signal) => Promise<T>` contract. Extracted
 * from {@link useContinueStream} for modularity (RULE-04); behavior is
 * unchanged.
 *
 * ADR-043 compliance — the bridge mechanism:
 *   - The first chunk calls `notifyData` (loading → streaming, resets the
 *     connection-loss timer), inserts the AI-annotation pending mark; further
 *     chunks append to it.
 *   - Stream completion resolves the promise after finalizing the pending mark.
 *   - `onError` rejects so useAIOperation's error mapper drives UI state.
 *   - cancel/abort is translated to an AbortError rejection (swallowed → idle).
 *
 * @module continueStream
 */

import type { Editor } from "@tiptap/react";
import type { MutableRefObject } from "react";
import {
  appendToPendingMark,
  finalizePendingMark,
  insertAIContent,
} from "@/components/studio/editor/extensions/AIAnnotation";
import { type ExtendLength, streamExtend } from "@/lib/api/generation";

/** Staged extend request — built by the hook at handleExtend time. */
export interface ExtendRequestParams {
  readonly textBefore: string;
  readonly textAfter: string | null;
  readonly selectedLength: ExtendLength;
}

/** Inputs for one continue/extend stream execution. */
export interface ContinueStreamParams {
  /** Editor captured at execution time (null/destroyed → resolve immediately). */
  readonly editor: Editor | null;
  /** Staged request (null → resolve immediately). */
  readonly request: ExtendRequestParams | null;
  readonly chapterId: string;
  readonly novelId: string;
  readonly tone: string | undefined;
  readonly locale: string;
  readonly signal: AbortSignal;
  /** useAIOperation lifecycle action (loading → streaming + timer reset). */
  readonly notifyData: () => void;
  /** Accumulated streamed text — state owned by the hook. */
  readonly accumulatedRef: MutableRefObject<string>;
}

/**
 * Run one continue/extend stream, resolving on completion and rejecting on
 * error/abort.
 *
 * Defensive: a start() without a staged request or a live editor resolves
 * without touching the transport.
 */
export function runContinueStream({
  editor,
  request,
  chapterId,
  novelId,
  tone,
  locale,
  signal,
  notifyData,
  accumulatedRef,
}: ContinueStreamParams): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    // Capture a local reference so closures spawned below always operate
    // on the editor instance current at execution time (useAIOperation
    // reads executeRef.current, which sees the latest render's editor).
    const ed = editor;
    const req = request;
    if (!ed || !req || ed.isDestroyed) {
      resolve();
      return;
    }

    let settled = false;
    let isFirstChunk = true;

    const onAbort = () => {
      if (!settled) {
        settled = true;
        reject(new DOMException("Aborted", "AbortError"));
      }
    };
    signal.addEventListener("abort", onAbort, { once: true });

    streamExtend(
      chapterId,
      novelId,
      {
        text_before: req.textBefore,
        text_after: req.textAfter,
        length: req.selectedLength,
        tone,
        language: locale,
      },
      {
        onChunk: (text) => {
          if (ed.isDestroyed) return;
          if (isFirstChunk) {
            notifyData();
            isFirstChunk = false;
          }

          const localId = `extend-${Date.now()}`;
          if (accumulatedRef.current.length === 0) {
            insertAIContent(ed, null, text, localId, "extend");
          } else {
            appendToPendingMark(ed, text);
          }
          accumulatedRef.current += text;
        },
        onComplete: () => {
          if (!settled) {
            settled = true;
            signal.removeEventListener("abort", onAbort);
            if (!ed.isDestroyed) {
              finalizePendingMark(ed, accumulatedRef.current);
            }
            resolve();
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
