/**
 * Generation AI streaming operation extracted from generationPanelController
 * (RULE-04 / AUFG-03-04).
 *
 * Wraps the chapter-generation SSE flow in `useAIOperation` so it gets
 * the §16 lifecycle (loading/streaming/error/connection-lost) and the
 * shared AbortController + retry machinery. Accumulates draft text,
 * word count, token usage and context metadata as chunks arrive.
 */

import type { Dispatch, SetStateAction } from "react";
import {
  type ContextMeta,
  type GenerateRequest,
  streamGeneration,
  writingApi,
} from "@/lib/api/generation";
import { SSEStreamError } from "@/lib/api/streaming";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import type { TokenUsage } from "@/types";

interface UseGenerationStreamParams {
  chapterId: string;
  novelId: string;
  lastParamsRef: React.MutableRefObject<GenerateRequest | null>;
  setRequestId: Dispatch<SetStateAction<string | null>>;
  setDraftText: Dispatch<SetStateAction<string>>;
  setWordCount: Dispatch<SetStateAction<number>>;
  setTokenUsage: Dispatch<SetStateAction<TokenUsage | null>>;
  setContextMeta: Dispatch<SetStateAction<ContextMeta | null>>;
  onChunkNotify: () => void;
}

interface UseGenerationStreamResult {
  state: ReturnType<typeof useAIOperation<null>>["state"];
  start: () => void;
  cancel: () => void;
  retry: () => void;
  isIdle: boolean;
  isLoading: boolean;
  isStreaming: boolean;
  isComplete: boolean;
  isConnectionLost: boolean;
}

export function useGenerationStream({
  chapterId,
  novelId,
  lastParamsRef,
  setRequestId,
  setDraftText,
  setWordCount,
  setTokenUsage,
  setContextMeta,
  onChunkNotify,
}: UseGenerationStreamParams): UseGenerationStreamResult {
  return useAIOperation<null>({
    execute: async (signal) => {
      const req = lastParamsRef.current!;
      const data = await writingApi.startGeneration(chapterId, novelId, req);
      const rid = data.request_id;
      setRequestId(rid);
      setDraftText("");
      setWordCount(0);
      setTokenUsage(null);
      setContextMeta(null);
      let sawFinalChunk = false;
      await streamGeneration(
        rid,
        (chunk) => {
          onChunkNotify();
          if (chunk.is_final) sawFinalChunk = true;
          setDraftText((prev) => prev + chunk.text);
          setWordCount((prev) => prev + chunk.text.split(/\s+/).filter(Boolean).length);
        },
        undefined,
        (err) => {
          throw err;
        },
        signal,
        setTokenUsage,
        setContextMeta,
      );
      // Audit M06: a generation stream that ends without an is_final chunk
      // died silently (TestModel retry exhaustion / provider drop). Treat it
      // as a stream error — NOT a completed draft — so the panel never
      // reaches the review phase with an empty draft.
      if (!sawFinalChunk) {
        throw new SSEStreamError("Generation stream ended without a final chunk", "stream");
      }
      return null;
    },
    connectionLossTimeout: 15_000,
  });
}
