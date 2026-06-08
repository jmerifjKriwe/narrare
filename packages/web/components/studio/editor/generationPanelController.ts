"use client";

/**
 * Generation panel controller — manages chapter generation lifecycle via useAIOperation.
 *
 * Replaces the previous manual AbortController + useMutation pattern with the shared
 * AI operation primitive (§16, ADR-043). Provides:
 * - Unified lifecycle: idle → loading → streaming → complete → error | connection_lost
 * - Server-side cancel via writingApi.stopGeneration + hook-level AbortController
 * - Structured AIErrorResponse instead of raw error.message mapping
 * - Connection-loss detection with partial output preservation
 */

import { useMutation } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

import {
  type ContextMeta,
  type GenerateRequest,
  type GenerationMode,
  streamGeneration,
  writingApi,
} from "@/lib/api/generation";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { useMemoryStatus, useRecordFeedback } from "@/lib/hooks/useMemory";
import type { FeedbackRequest, TokenUsage } from "@/types";

type PanelPhase = "config" | "streaming" | "review" | "error";
type RatingAction = "accept" | "reject";

interface ControllerArgs {
  novelId: string;
  chapterId: string;
  onDraftAccepted: (text: string) => void;
  t: (key: string, params?: Record<string, string | number | Date>) => string;
}

export function useGenerationPanelController({
  novelId,
  chapterId,
  onDraftAccepted,
  t: _t,
}: ControllerArgs) {
  const [mode, setMode] = useState<GenerationMode>("full_draft");
  const [outline, setOutline] = useState("");
  const [prompt, setPrompt] = useState("");
  const [wordTarget, setWordTarget] = useState<number>(0);
  const [tone, setTone] = useState("balanced");
  const [draftText, setDraftText] = useState("");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [wordCount, setWordCount] = useState(0);
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | null>(null);
  const [contextMeta, setContextMeta] = useState<ContextMeta | null>(null);
  const [showRating, setShowRating] = useState<RatingAction | null>(null);
  const [stoppedWithOutput, setStoppedWithOutput] = useState(false);
  const lastParamsRef = useRef<GenerateRequest | null>(null);
  const originalTextRef = useRef<string>("");
  const recordFeedback = useRecordFeedback(novelId);
  const { eventCount } = useMemoryStatus(novelId);

  const buildRequest = useCallback((): GenerateRequest => {
    const req: GenerateRequest = {
      mode,
      word_target: wordTarget > 0 ? wordTarget : null,
      tone,
    };
    if (mode === "full_draft" || mode === "scene_by_scene") req.outline = outline || null;
    if (mode === "full_draft" || mode === "interview_assisted") req.prompt = prompt || null;
    if (mode === "interview_assisted") req.auto_continue = true;
    return req;
  }, [mode, outline, prompt, wordTarget, tone]);

  const {
    state,
    start,
    cancel,
    notifyData,
    retry,
    isIdle,
    isLoading,
    isStreaming,
    isComplete,
    isConnectionLost,
  } = useAIOperation<null>({
    execute: async (signal) => {
      const req = lastParamsRef.current!;
      const data = await writingApi.startGeneration(chapterId, novelId, req);
      const rid = data.request_id;

      setRequestId(rid);
      setDraftText("");
      setWordCount(0);
      setTokenUsage(null);
      setContextMeta(null);
      setShowRating(null);
      setStoppedWithOutput(false);
      originalTextRef.current = "";

      await streamGeneration(
        rid,
        (chunk) => {
          notifyData();
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

      return null;
    },
    connectionLossTimeout: 15_000,
  });

  // -- Derived phase from hook state + stopped-with-output flag --

  const phase: PanelPhase = stoppedWithOutput
    ? "review"
    : isIdle
      ? "config"
      : isLoading || isStreaming
        ? "streaming"
        : isComplete
          ? "review"
          : "error";

  // -- Mutation wrappers for accept/reject (REST calls, not AI operations) --

  const acceptMutation = useMutation({
    mutationFn: () => writingApi.acceptDraft(requestId!),
    onSuccess: () => {
      if (!originalTextRef.current) originalTextRef.current = draftText;
      onDraftAccepted(draftText);
      setShowRating("accept");
    },
  });
  const rejectMutation = useMutation({
    mutationFn: () => writingApi.rejectDraft(requestId!),
    onSuccess: () => {
      if (!originalTextRef.current) originalTextRef.current = draftText;
      setShowRating("reject");
    },
  });

  // -- Handlers --

  const handleGenerate = useCallback(() => {
    setStoppedWithOutput(false);
    const req = buildRequest();
    lastParamsRef.current = req;
    start();
  }, [buildRequest, start]);

  const handleStop = useCallback(async () => {
    if (requestId) {
      await writingApi.stopGeneration(requestId).catch(() => {});
    }
    cancel();

    if (draftText) {
      setStoppedWithOutput(true);
    }
  }, [requestId, draftText, cancel]);

  const handleRegenerate = useCallback(async () => {
    if (requestId) {
      await writingApi.rejectDraft(requestId).catch(() => {});
    }
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
  }, [requestId, buildRequest, start]);

  const handleRetry = useCallback(() => {
    setStoppedWithOutput(false);
    retry();
  }, [retry]);

  const handleRatingDone = useCallback(
    (rating?: number, reason?: string) => {
      if (showRating) {
        const originalText = originalTextRef.current;
        const isModified = originalText !== draftText && originalText.length > 0;
        const action: FeedbackRequest["action"] =
          showRating === "accept" ? (isModified ? "modify" : "accept") : "reject";
        recordFeedback.mutate(
          {
            action,
            suggestion_id: requestId ?? "",
            intent: mode,
            suggestion_text: originalText || draftText,
            modification: isModified ? draftText : undefined,
            rating: rating ?? undefined,
            context: reason ? { reject_reason: reason } : undefined,
            project_id: novelId,
            chapter_id: chapterId,
            mode,
          },
          { onError: () => undefined },
        );
      }
      setStoppedWithOutput(false);
      setDraftText("");
      setRequestId(null);
      setShowRating(null);
      originalTextRef.current = "";
      setContextMeta(null);
    },
    [showRating, draftText, requestId, mode, novelId, chapterId, recordFeedback],
  );

  return {
    acceptMutation,
    connectionLost: isConnectionLost,
    contextMeta,
    draftText,
    /** Structured AIErrorResponse (null when no error). §16.5 */
    error: state.error,
    /** Resolved user-visible error message string (null when no error). */
    errorMsg: state.error?.userMessage ?? null,
    eventCount,
    /** True while the AI operation is loading (before first streaming chunk). */
    isLoading,
    handleGenerate,
    handleRatingDone,
    handleRegenerate,
    handleRetry,
    handleStop,
    mode,
    outline,
    /** Derived panel phase from AI operation status. */
    phase,
    prompt,
    rejectMutation,
    setMode,
    setOutline,
    setPrompt,
    setTone,
    setWordTarget,
    showRating,
    tokenUsage,
    tone,
    wordCount,
    wordTarget,
    targetNum: wordTarget > 0 ? wordTarget : 3000,
    acceptDraft: () => {
      if (!originalTextRef.current) originalTextRef.current = draftText;
      acceptMutation.mutate();
    },
    rejectDraft: () => {
      if (!originalTextRef.current) originalTextRef.current = draftText;
      rejectMutation.mutate();
    },
  };
}
