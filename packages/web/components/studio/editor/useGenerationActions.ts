/**
 * Generation action handlers extracted from generationPanelController
 * (RULE-04 / AUFG-03-04).
 *
 * Wraps the stop/regenerate/retry actions that coordinate the streaming
 * operation with server-side cancel/reject and partial-output preservation.
 */

import { type Dispatch, type MutableRefObject, type SetStateAction, useCallback } from "react";
import { type ContextMeta, type GenerateRequest, writingApi } from "@/lib/api/generation";

interface UseGenerationActionsParams {
  requestId: string | null;
  draftText: string;
  lastParamsRef: MutableRefObject<GenerateRequest | null>;
  buildRequest: () => GenerateRequest;
  start: () => void;
  cancel: () => void;
  retry: () => void;
  setStoppedWithOutput: (value: boolean) => void;
  setDraftText: (value: string) => void;
  setRequestId: (value: string | null) => void;
  setContextMeta: Dispatch<SetStateAction<ContextMeta | null>>;
  setShowRating: Dispatch<SetStateAction<"accept" | "reject" | null>>;
  originalTextRef: MutableRefObject<string>;
}

interface UseGenerationActionsResult {
  handleStop: () => Promise<void>;
  handleRegenerate: () => Promise<void>;
  handleRetry: () => void;
}

export function useGenerationActions({
  requestId,
  draftText,
  lastParamsRef,
  buildRequest,
  start,
  cancel,
  retry,
  setStoppedWithOutput,
  setDraftText,
  setRequestId,
  setContextMeta,
  setShowRating,
  originalTextRef,
}: UseGenerationActionsParams): UseGenerationActionsResult {
  const handleStop = useCallback(async () => {
    if (requestId) await writingApi.stopGeneration(requestId).catch(() => {});
    cancel();
    if (draftText) setStoppedWithOutput(true);
  }, [requestId, draftText, cancel, setStoppedWithOutput]);

  const handleRegenerate = useCallback(async () => {
    if (requestId) await writingApi.rejectDraft(requestId).catch(() => {});
    setDraftText("");
    setRequestId(null);
    setStoppedWithOutput(false);
    setContextMeta(null);
    setShowRating(null);
    originalTextRef.current = "";
    if (lastParamsRef.current) {
      lastParamsRef.current = buildRequest();
      start();
    }
  }, [
    requestId,
    buildRequest,
    start,
    setDraftText,
    setRequestId,
    setStoppedWithOutput,
    setContextMeta,
    setShowRating,
    originalTextRef,
    lastParamsRef,
  ]);

  const handleRetry = useCallback(() => {
    setStoppedWithOutput(false);
    retry();
  }, [retry, setStoppedWithOutput]);

  return { handleStop, handleRegenerate, handleRetry };
}
