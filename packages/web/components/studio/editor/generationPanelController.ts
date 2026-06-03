import { useMutation } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import {
  type ContextMeta,
  type GenerateRequest,
  type GenerationMode,
  streamGeneration,
  writingApi,
} from "@/lib/api/generation";
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
  t,
}: ControllerArgs) {
  const [mode, setMode] = useState<GenerationMode>("full_draft");
  const [outline, setOutline] = useState("");
  const [prompt, setPrompt] = useState("");
  const [wordTarget, setWordTarget] = useState<number>(0);
  const [tone, setTone] = useState("balanced");
  const [phase, setPhase] = useState<PanelPhase>("config");
  const [draftText, setDraftText] = useState("");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [wordCount, setWordCount] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [connectionLost, setConnectionLost] = useState(false);
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | null>(null);
  const [contextMeta, setContextMeta] = useState<ContextMeta | null>(null);
  const [showRating, setShowRating] = useState<RatingAction | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastParamsRef = useRef<GenerateRequest | null>(null);
  const originalTextRef = useRef<string>("");
  const recordFeedback = useRecordFeedback(novelId);
  const { eventCount } = useMemoryStatus(novelId);

  const buildRequest = useCallback((): GenerateRequest => {
    const req: GenerateRequest = { mode, word_target: wordTarget > 0 ? wordTarget : null, tone };
    if (mode === "full_draft" || mode === "scene_by_scene") req.outline = outline || null;
    if (mode === "full_draft" || mode === "interview_assisted") req.prompt = prompt || null;
    if (mode === "interview_assisted") req.auto_continue = true;
    return req;
  }, [mode, outline, prompt, wordTarget, tone]);

  const startMutation = useMutation({
    mutationFn: (req: GenerateRequest) => writingApi.startGeneration(chapterId, novelId, req),
    onSuccess: async (data) => {
      setRequestId(data.request_id);
      setPhase("streaming");
      setDraftText("");
      setWordCount(0);
      setErrorMsg(null);
      setConnectionLost(false);
      setShowRating(null);
      originalTextRef.current = "";
      setContextMeta(null);
      setTokenUsage(null);

      const controller = new AbortController();
      abortRef.current = controller;
      await streamGeneration(
        data.request_id,
        (chunk) => {
          setDraftText((prev) => prev + chunk.text);
          setWordCount((prev) => prev + chunk.text.split(/\s+/).filter(Boolean).length);
        },
        () => {
          setPhase("review");
          abortRef.current = null;
        },
        (err) => {
          if (err.message.includes("HTTP")) {
            setErrorMsg(err.message);
            setPhase("error");
          } else {
            setConnectionLost(true);
          }
          abortRef.current = null;
        },
        controller.signal,
        setTokenUsage,
        setContextMeta,
      );
    },
    onError: (err: unknown) => setStartError(err),
  });

  function setStartError(err: unknown) {
    const msg = err instanceof Error ? err.message : "";
    if (msg.includes("MISSING_INPUT") || msg.includes("At least one")) {
      setErrorMsg(t("generationPanel.validationMissingInput"));
    } else if (msg.includes("CONTEXT_TOO_LARGE") || msg.includes("context_too_large")) {
      if (msg.includes("outline") || msg.includes("OUTLINE")) {
        setErrorMsg(t("generationPanel.contextTooLargeOutline", { max: 8000 }));
      } else if (msg.includes("pinned") || msg.includes("PINNED") || msg.includes("kb_entries")) {
        setErrorMsg(t("generationPanel.contextTooLargePinned"));
      } else setErrorMsg(t("generationPanel.contextTooLargeGeneric"));
    } else setErrorMsg(msg || t("generationPanel.startFailed"));
    setPhase("error");
  }

  const handleGenerate = useCallback(() => {
    const req = buildRequest();
    lastParamsRef.current = req;
    startMutation.mutate(req);
  }, [buildRequest, startMutation]);

  const handleStop = useCallback(async () => {
    abortRef.current?.abort();
    if (requestId) await writingApi.stopGeneration(requestId);
    setPhase(draftText ? "review" : "config");
  }, [requestId, draftText]);

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
      setPhase("config");
      setDraftText("");
      setRequestId(null);
      setShowRating(null);
      originalTextRef.current = "";
      setContextMeta(null);
    },
    [showRating, draftText, requestId, mode, novelId, chapterId, recordFeedback],
  );

  const handleRegenerate = useCallback(async () => {
    if (requestId) await writingApi.rejectDraft(requestId);
    setDraftText("");
    setRequestId(null);
    setPhase("config");
    setContextMeta(null);
    if (lastParamsRef.current) startMutation.mutate(lastParamsRef.current);
  }, [requestId, startMutation]);

  const handleRetry = useCallback(() => {
    setConnectionLost(false);
    setErrorMsg(null);
    if (lastParamsRef.current) startMutation.mutate(lastParamsRef.current);
  }, [startMutation]);

  return {
    acceptMutation,
    connectionLost,
    contextMeta,
    draftText,
    errorMsg,
    eventCount,
    handleGenerate,
    handleRatingDone,
    handleRegenerate,
    handleRetry,
    handleStop,
    mode,
    outline,
    phase,
    prompt,
    rejectMutation,
    setMode,
    setOutline,
    setPrompt,
    setTone,
    setWordTarget,
    showRating,
    startMutation,
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
