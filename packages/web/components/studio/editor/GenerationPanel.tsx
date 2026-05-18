"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, RotateCcw, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useRef, useState } from "react";
import {
  type GenerateRequest,
  type GenerationMode,
  streamGeneration,
  writingApi,
} from "@/lib/api/generation";
import { GenerationConfig } from "./GenerationConfig";
import { GenerationDraft } from "./GenerationDraft";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GenerationPanelProps {
  readonly novelId: string;
  readonly chapterId: string;
  readonly chapterContent: string;
  readonly onDraftAccepted: (text: string) => void;
  readonly onClose: () => void;
  readonly onStartSession?: (mode: string) => void;
}

type PanelPhase = "config" | "streaming" | "review" | "error";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GenerationPanel({
  novelId,
  chapterId,
  chapterContent: _chapterContent,
  onDraftAccepted,
  onClose,
  onStartSession,
}: GenerationPanelProps) {
  const t = useTranslations("studio");

  // Config state
  const [mode, setMode] = useState<GenerationMode>("full_draft");
  const [outline, setOutline] = useState("");
  const [prompt, setPrompt] = useState("");
  const [wordTarget, setWordTarget] = useState<number>(0);
  const [tone, setTone] = useState("balanced");

  // Generation state
  const [phase, setPhase] = useState<PanelPhase>("config");
  const [draftText, setDraftText] = useState("");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [wordCount, setWordCount] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [connectionLost, setConnectionLost] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const lastParamsRef = useRef<GenerateRequest | null>(null);

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  const buildRequest = useCallback((): GenerateRequest => {
    const req: GenerateRequest = {
      mode,
      word_target: wordTarget > 0 ? wordTarget : null,
      tone,
    };
    if (mode === "full_draft" || mode === "scene_by_scene") {
      req.outline = outline || null;
    }
    if (mode === "full_draft" || mode === "interview_assisted") {
      req.prompt = prompt || null;
    }
    if (mode === "interview_assisted") {
      req.auto_continue = true;
    }
    return req;
  }, [mode, outline, prompt, wordTarget, tone]);

  // ---------------------------------------------------------------------------
  // Start generation
  // ---------------------------------------------------------------------------

  const startMutation = useMutation({
    mutationFn: (req: GenerateRequest) => writingApi.startGeneration(chapterId, novelId, req),
    onSuccess: async (data) => {
      setRequestId(data.request_id);
      setPhase("streaming");
      setDraftText("");
      setWordCount(0);
      setErrorMsg(null);
      setConnectionLost(false);

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
      );
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("MISSING_INPUT") || msg.includes("At least one")) {
        setErrorMsg(t("generationPanel.validationMissingInput"));
      } else {
        setErrorMsg(msg || t("generationPanel.startFailed"));
      }
      setPhase("error");
    },
  });

  const handleGenerate = useCallback(() => {
    const req = buildRequest();
    lastParamsRef.current = req;
    startMutation.mutate(req);
  }, [buildRequest, startMutation]);

  // ---------------------------------------------------------------------------
  // Stop / Accept / Reject / Regenerate
  // ---------------------------------------------------------------------------

  const handleStop = useCallback(async () => {
    abortRef.current?.abort();
    if (requestId) await writingApi.stopGeneration(requestId);
    setPhase(draftText ? "review" : "config");
  }, [requestId, draftText]);

  const acceptMutation = useMutation({
    mutationFn: () => writingApi.acceptDraft(requestId!),
    onSuccess: () => {
      onDraftAccepted(draftText);
      setPhase("config");
      setDraftText("");
      setRequestId(null);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => writingApi.rejectDraft(requestId!),
    onSuccess: () => {
      setPhase("config");
      setDraftText("");
      setRequestId(null);
    },
  });

  const handleRegenerate = useCallback(async () => {
    if (requestId) await writingApi.rejectDraft(requestId);
    setDraftText("");
    setRequestId(null);
    setPhase("config");
    if (lastParamsRef.current) {
      startMutation.mutate(lastParamsRef.current);
    }
  }, [requestId, startMutation]);

  // ---------------------------------------------------------------------------
  // Retry (connection lost)
  // ---------------------------------------------------------------------------

  const handleRetry = useCallback(() => {
    setConnectionLost(false);
    setErrorMsg(null);
    if (lastParamsRef.current) {
      startMutation.mutate(lastParamsRef.current);
    }
  }, [startMutation]);

  // ---------------------------------------------------------------------------
  // Derived values
  // ---------------------------------------------------------------------------

  const targetNum = wordTarget > 0 ? wordTarget : 3000;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full border-l border-border bg-card w-80">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Sparkles className="w-4 h-4 text-primary" />
          <span>{t("generationPanel.title")}</span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 rounded-md hover:bg-accent transition-colors"
          aria-label={t("generationPanel.close")}
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
        {/* Config phase */}
        {phase === "config" && (
          <GenerationConfig
            mode={mode}
            setMode={setMode}
            outline={outline}
            setOutline={setOutline}
            prompt={prompt}
            setPrompt={setPrompt}
            wordTarget={wordTarget}
            setWordTarget={setWordTarget}
            tone={tone}
            setTone={setTone}
            isPending={startMutation.isPending}
            onGenerate={handleGenerate}
            onStartSession={onStartSession}
          />
        )}

        {/* Streaming / Review phase */}
        {(phase === "streaming" || phase === "review") && (
          <GenerationDraft
            phase={phase}
            draftText={draftText}
            wordCount={wordCount}
            targetNum={targetNum}
            isAcceptPending={acceptMutation.isPending}
            isRejectPending={rejectMutation.isPending}
            onStop={handleStop}
            onAccept={() => acceptMutation.mutate()}
            onReject={() => rejectMutation.mutate()}
            onRegenerate={handleRegenerate}
          />
        )}

        {/* Error state */}
        {phase === "error" && (
          <div className="flex flex-col gap-3">
            <div className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm" role="alert">
              {errorMsg || t("generationPanel.unknownError")}
            </div>
            <button
              type="button"
              onClick={handleRetry}
              className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <RotateCcw className="w-4 h-4" />
              <span>{t("generationPanel.retry")}</span>
            </button>
          </div>
        )}
      </div>

      {/* Connection lost banner */}
      {connectionLost && (
        <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-t border-border bg-yellow-500/10">
          <div className="flex items-center gap-2 text-sm text-yellow-700 dark:text-yellow-400">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{t("generationPanel.connectionLost")}</span>
          </div>
          <button
            type="button"
            onClick={handleRetry}
            className="px-3 py-1 text-xs font-medium rounded-md bg-yellow-600 text-white hover:bg-yellow-700 transition-colors"
          >
            {t("generationPanel.retry")}
          </button>
        </div>
      )}
    </div>
  );
}
