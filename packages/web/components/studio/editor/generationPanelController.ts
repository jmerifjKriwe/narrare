"use client";

/**
 * Generation panel controller — thin composer (RULE-04 / AUFG-03-04).
 *
 * Replaces the previous manual AbortController + useMutation pattern with
 * the shared AI operation primitive (§16, ADR-043). Responsibilities are
 * delegated to focused sub-hooks:
 *
 * - {@link useGenerationConfig} — form state + request builder.
 * - {@link useGenerationStream} — AI streaming lifecycle (useAIOperation).
 * - {@link useGenerationRating} — accept/reject feedback to memory service.
 * - {@link useGenerationActions} — stop/regenerate/retry coordination.
 */

import { useRef, useState } from "react";
import type { ContextMeta, GenerateRequest } from "@/lib/api/generation";
import { useMemoryStatus } from "@/lib/hooks/useMemory";
import type { TokenUsage } from "@/types";
import type { ScenePlan } from "@/types/planning";
import { useGenerationActions } from "./useGenerationActions";
import { useGenerationConfig } from "./useGenerationConfig";
import { useGenerationMutations } from "./useGenerationMutations";
import { useGenerationRating } from "./useGenerationRating";
import { useGenerationStream } from "./useGenerationStream";

interface ControllerArgs {
  novelId: string;
  chapterId: string;
  onDraftAccepted: (text: string) => void;
  t: (key: string, params?: Record<string, string | number | Date>) => string;
  /** Chapter scene plans (spec §8.1), injected from useScenePlans — see useGenerationConfig. */
  scenePlans?: ScenePlan[] | null;
}

export function useGenerationPanelController({
  novelId,
  chapterId,
  onDraftAccepted,
  t: _t,
  scenePlans,
}: ControllerArgs) {
  const config = useGenerationConfig({ scenePlans });
  const [draftText, setDraftText] = useState("");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [wordCount, setWordCount] = useState(0);
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | null>(null);
  const [contextMeta, setContextMeta] = useState<ContextMeta | null>(null);
  const [stoppedWithOutput, setStoppedWithOutput] = useState(false);
  const lastParamsRef = useRef<GenerateRequest | null>(null);
  const originalTextRef = useRef<string>("");
  const { eventCount } = useMemoryStatus(novelId);

  const stream = useGenerationStream({
    chapterId,
    novelId,
    lastParamsRef,
    setRequestId,
    setDraftText,
    setWordCount,
    setTokenUsage,
    setContextMeta,
    onChunkNotify: () => {
      setStoppedWithOutput(false);
      originalTextRef.current = "";
    },
  });

  const rating = useGenerationRating({
    novelId,
    chapterId,
    mode: config.mode,
    draftText,
    requestId,
    originalTextRef,
  });

  const actions = useGenerationActions({
    requestId,
    draftText,
    lastParamsRef,
    buildRequest: config.buildRequest,
    start: stream.start,
    cancel: stream.cancel,
    retry: stream.retry,
    setStoppedWithOutput,
    setDraftText,
    setRequestId,
    setContextMeta,
    setShowRating: rating.setShowRating,
    originalTextRef,
  });

  const phase = useGenerationMutations({
    requestId,
    draftText,
    stoppedWithOutput,
    stream,
    rating,
    onDraftAccepted,
  });

  const handleGenerate = () => {
    setStoppedWithOutput(false);
    lastParamsRef.current = config.buildRequest();
    stream.start();
  };

  return {
    acceptMutation: phase.acceptMutation,
    acceptDraft: () => {
      rating.captureOriginal();
      phase.acceptMutation.mutate();
    },
    connectionLost: stream.isConnectionLost,
    contextMeta,
    draftText,
    error: stream.state.error,
    errorMsg: stream.state.error?.userMessage ?? null,
    eventCount,
    handleGenerate,
    handleRatingDone: rating.handleRatingDone,
    handleRegenerate: actions.handleRegenerate,
    handleRetry: actions.handleRetry,
    handleStop: actions.handleStop,
    isLoading: stream.isLoading,
    mode: config.mode,
    outline: config.outline,
    phase: phase.phase,
    prompt: config.prompt,
    rejectDraft: () => {
      rating.captureOriginal();
      phase.rejectMutation.mutate();
    },
    rejectMutation: phase.rejectMutation,
    setMode: config.setMode,
    setOutline: config.setOutline,
    setPrompt: config.setPrompt,
    setTone: config.setTone,
    setUseScenePlans: config.setUseScenePlans,
    setWordTarget: config.setWordTarget,
    showRating: rating.showRating,
    targetNum: config.wordTarget > 0 ? config.wordTarget : 3000,
    tokenUsage,
    tone: config.tone,
    useScenePlans: config.useScenePlans,
    wordCount,
    wordTarget: config.wordTarget,
  };
}
