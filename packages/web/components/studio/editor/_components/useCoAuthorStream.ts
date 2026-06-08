"use client";

/**
 * Co-Author streaming hook — wraps useAIOperation for the Co-Author SSE lifecycle.
 *
 * Manages streamed text accumulation, revision data, and the streaming
 * operation state. Extracted from useCoAuthorPanel for modularity (RULE-04).
 *
 * @module useCoAuthorStream
 */

import { useState } from "react";
import {
  type ChangeDetail,
  type CoAuthorFocus,
  type CoAuthorRevision,
  streamCoAuthor,
} from "@/lib/api/coauthor";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { createAcceptanceMap } from "./coauthor-message-utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UseCoAuthorStreamParams {
  readonly novelId: string;
  readonly chapterId: string;
  readonly selectionText: string;
  readonly contextBefore?: string;
  readonly contextAfter?: string;
  readonly selectedFocus: readonly CoAuthorFocus[];
  readonly setChanges: React.Dispatch<React.SetStateAction<ChangeDetail[]>>;
  readonly setAcceptance: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  readonly onSuccess?: (revision: CoAuthorRevision) => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Encapsulates the Co-Author SSE streaming operation.
 *
 * Owns the `streamedText`, `reasoning`, and `requestId` state that accumulates
 * during the streaming phase. Delegates `changes` and `acceptance` state
 * management to the caller (via setChanges / setAcceptance).
 */
export function useCoAuthorStream({
  novelId,
  chapterId,
  selectionText,
  contextBefore,
  contextAfter,
  selectedFocus,
  setChanges,
  setAcceptance,
  onSuccess,
}: UseCoAuthorStreamParams) {
  const [streamedText, setStreamedText] = useState("");
  const [reasoning, setReasoning] = useState("");
  const [requestId, setRequestId] = useState<string>("");

  const aiOp = useAIOperation<CoAuthorRevision | null>({
    execute: async (signal) => {
      setStreamedText("");
      setChanges([]);
      setReasoning("");
      setRequestId(crypto.randomUUID());

      let revision: CoAuthorRevision | null = null;

      await streamCoAuthor(
        chapterId,
        novelId,
        {
          selection_text: selectionText,
          context_before: contextBefore,
          context_after: contextAfter,
          focus: [...selectedFocus],
        },
        {
          onChunk: (text) => {
            aiOp.notifyData();
            setStreamedText((prev) => prev + text);
          },
          onComplete: (rev) => {
            revision = rev;
            setChanges(rev.changes);
            setReasoning(rev.reasoning);
            if (rev.request_id) setRequestId(rev.request_id);
            setAcceptance(createAcceptanceMap(rev.changes, true));
          },
          onError: (err) => {
            throw err;
          },
        },
        signal,
      );

      return revision;
    },
    onSuccess: (revision) => {
      if (revision) {
        onSuccess?.(revision);
      }
    },
    connectionLossTimeout: 15_000,
  });

  return {
    streamedText,
    reasoning,
    requestId,
    state: aiOp.state,
    start: aiOp.start,
    cancel: aiOp.cancel,
    retry: aiOp.retry,
    isLoading: aiOp.isLoading,
    isStreaming: aiOp.isStreaming,
    isComplete: aiOp.isComplete,
    isError: aiOp.isError,
    isConnectionLost: aiOp.isConnectionLost,
  };
}
