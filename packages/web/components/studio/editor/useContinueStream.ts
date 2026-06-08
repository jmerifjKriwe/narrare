"use client";

/**
 * Continue-streaming hook for the AI "continue writing" feature.
 *
 * Wraps useAIOperation with the TipTap-specific streaming logic
 * (insertAIContent, appendToPendingMark, finalizePendingMark).
 * Extracted from ContinueButton for modularity (RULE-04).
 *
 * @module useContinueStream
 */

import type { Editor } from "@tiptap/react";
import { useLocale } from "next-intl";
import { useCallback, useRef } from "react";
import {
  appendToPendingMark,
  finalizePendingMark,
  insertAIContent,
} from "@/components/studio/editor/extensions/AIAnnotation";
import { type ExtendLength, streamExtend } from "@/lib/api/generation";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ExtendRequestParams {
  readonly textBefore: string;
  readonly textAfter: string | null;
  readonly selectedLength: ExtendLength;
}

interface UseContinueStreamParams {
  readonly editor: Editor;
  readonly chapterId: string;
  readonly novelId: string;
  readonly tone?: string;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useContinueStream({ editor, chapterId, novelId, tone }: UseContinueStreamParams) {
  const locale = useLocale();
  const accumulatedRef = useRef("");
  const requestRef = useRef<ExtendRequestParams | null>(null);

  // -- AI operation lifecycle via useAIOperation --

  const { start, cancel, notifyData, isLoading, isStreaming } = useAIOperation<void>({
    execute: (signal) =>
      new Promise<void>((resolve, reject) => {
        const req = requestRef.current;
        if (!req || editor.isDestroyed) {
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
              if (editor.isDestroyed) return;
              if (isFirstChunk) {
                notifyData();
                isFirstChunk = false;
              }

              const localId = `extend-${Date.now()}`;
              if (accumulatedRef.current.length === 0) {
                insertAIContent(editor, null, text, localId, "extend");
              } else {
                appendToPendingMark(editor, text);
              }
              accumulatedRef.current += text;
            },
            onComplete: () => {
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                if (!editor.isDestroyed) {
                  finalizePendingMark(editor, accumulatedRef.current);
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
      }),
    connectionLossTimeout: 15_000,
  });

  const handleExtend = useCallback(
    (selectedLength: ExtendLength) => {
      if (isLoading || isStreaming) return;
      if (editor.isDestroyed) return;

      const $head = editor.state.selection.$head;
      const textBefore = $head.parent.textContent.slice(0, $head.parentOffset);
      const textAfter = $head.parent.textContent.slice($head.parentOffset);

      requestRef.current = { textBefore, textAfter: textAfter || null, selectedLength };
      accumulatedRef.current = "";
      start();
    },
    [editor, isLoading, isStreaming, start],
  );

  const handleStop = useCallback(() => {
    cancel();
  }, [cancel]);

  return { handleExtend, handleStop, isLoading, isStreaming };
}
