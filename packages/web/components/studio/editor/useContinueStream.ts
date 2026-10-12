"use client";

/**
 * Continue-streaming hook for the AI "continue writing" feature.
 *
 * Wraps useAIOperation, delegating the TipTap-specific streaming bridge to
 * {@link runContinueStream} (insertAIContent, appendToPendingMark,
 * finalizePendingMark). Extracted from ContinueButton for modularity
 * (RULE-04).
 *
 * Null-safe by contract: the single stream instance is owned by EditorView
 * (B08 wiring, Task 11) and shared by toolbar, palette, and slash commands;
 * `useAIOperation` reads `executeRef.current`, so closures always see the
 * latest editor. Payload caps are enforced at extraction (ExtendRequest:
 * text_before ≤ 10 000, text_after ≤ 2 000 chars).
 *
 * @module useContinueStream
 */

import type { Editor } from "@tiptap/react";
import { useLocale } from "next-intl";
import { useCallback, useRef } from "react";
import type { ExtendLength } from "@/lib/api/generation";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { type ExtendRequestParams, runContinueStream } from "./continueStream";

interface UseContinueStreamParams {
  /** Nullable: the stream owner (EditorView) may not have mounted the editor yet. */
  readonly editor: Editor | null;
  readonly chapterId: string;
  readonly novelId: string;
  readonly tone?: string;
}

export function useContinueStream({ editor, chapterId, novelId, tone }: UseContinueStreamParams) {
  const locale = useLocale();
  const accumulatedRef = useRef("");
  const requestRef = useRef<ExtendRequestParams | null>(null);

  // -- AI operation lifecycle via useAIOperation --

  const { start, cancel, notifyData, isLoading, isStreaming } = useAIOperation<void>({
    execute: (signal): Promise<void> =>
      runContinueStream({
        editor,
        request: requestRef.current,
        chapterId,
        novelId,
        tone,
        locale,
        signal,
        notifyData,
        accumulatedRef,
      }),
    connectionLossTimeout: 15_000,
  });

  const handleExtend = useCallback(
    (selectedLength: ExtendLength) => {
      if (isLoading || isStreaming) return;
      if (!editor || editor.isDestroyed) return;

      const $head = editor.state.selection.$head;
      // ExtendRequest caps: text_before ≤ 10 000, text_after ≤ 2 000 chars
      // (apps/api/narrare/writing/schemas.py) — clamp at extraction so the
      // payload is compliant by construction (same class as audit B01).
      const textBefore = $head.parent.textContent.slice(0, $head.parentOffset).slice(0, 10_000);
      const textAfter = $head.parent.textContent.slice($head.parentOffset).slice(0, 2_000);

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
