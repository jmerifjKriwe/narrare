"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, RotateCcw, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useRef, useState } from "react";
import { LearningStatus } from "@/components/studio/learning/LearningStatus";
import {
  type ContextMeta,
  type GenerateRequest,
  type GenerationMode,
  streamGeneration,
  writingApi,
} from "@/lib/api/generation";
import { useMemoryStatus, useRecordFeedback } from "@/lib/hooks/useMemory";
import type { FeedbackRequest, TokenUsage } from "@/types";
import { ContextInspector } from "./ContextInspector";
import { GenerationConfig } from "./GenerationConfig";
import { GenerationDraft } from "./GenerationDraft";
import { RatingPrompt } from "./RatingPrompt";

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
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | null>(null);
  const [contextMeta, setContextMeta] = useState<ContextMeta | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const lastParamsRef = useRef<GenerateRequest | null>(null);

  // --- Modify-tracking: store original text for diff on accept ---
  const originalTextRef = useRef<string>("");

  // --- Rating state ---
  const [showRating, setShowRating] = useState<"accept" | "reject" | null>(null);

  // --- Memory / learning hooks ---
  const recordFeedback = useRecordFeedback(novelId);
  const { eventCount } = useMemoryStatus(novelId);

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
      setShowRating(null);
      originalTextRef.current = "";
      setContextMeta(null);

      const controller = new AbortController();
      abortRef.current = controller;
      setTokenUsage(null);

      await streamGeneration(
        data.request_id,
        (chunk) => {
          setDraftText((prev) => prev + chunk.text);
          setWordCount((prev) => prev + chunk.text.split(/\s+/).filter(Boolean).length);
        },
        () => {
          setPhase("review");
          abortRef.current = null;
          // Store original text for modify-tracking (snapshot before any potential edit)
          // At this point, draftText is the full AI-generated text
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
        (usage) => {
          setTokenUsage(usage);
        },
        (meta) => {
          setContextMeta(meta);
        },
      );
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("MISSING_INPUT") || msg.includes("At least one")) {
        setErrorMsg(t("generationPanel.validationMissingInput"));
      } else if (msg.includes("CONTEXT_TOO_LARGE") || msg.includes("context_too_large")) {
        // Provide actionable guidance based on what's too large
        if (msg.includes("outline") || msg.includes("OUTLINE")) {
          setErrorMsg(t("generationPanel.contextTooLargeOutline", { max: 8000 }));
        } else if (msg.includes("pinned") || msg.includes("PINNED") || msg.includes("kb_entries")) {
          setErrorMsg(t("generationPanel.contextTooLargePinned"));
        } else {
          setErrorMsg(t("generationPanel.contextTooLargeGeneric"));
        }
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
      // Store original text for modify-tracking comparison
      if (!originalTextRef.current) {
        originalTextRef.current = draftText;
      }

      // Pass accepted text to editor immediately
      onDraftAccepted(draftText);
      // Show rating prompt — phase stays in "review" until rating is done
      setShowRating("accept");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => writingApi.rejectDraft(requestId!),
    onSuccess: () => {
      // Store original text for modify-tracking comparison
      if (!originalTextRef.current) {
        originalTextRef.current = draftText;
      }
      // Show rating prompt — phase stays in "review" until rating is done
      setShowRating("reject");
    },
  });

  /** Called after rating prompt is done (submit or dismiss) — resets to config. */
  const handleRatingDone = useCallback(
    (rating?: number, reason?: string) => {
      if (showRating) {
        const originalText = originalTextRef.current;
        const isModified = originalText !== draftText && originalText.length > 0;
        const action: FeedbackRequest["action"] =
          showRating === "accept" ? (isModified ? "modify" : "accept") : "reject";

        const feedbackData: FeedbackRequest = {
          action,
          suggestion_id: requestId ?? "",
          intent: mode,
          suggestion_text: originalText || draftText,
          modification: isModified ? draftText : undefined,
          rating: rating ?? undefined,
          context: reason ? { reject_reason: reason } : undefined,
          project_id: novelId,
          chapter_id: chapterId,
          mode: mode,
        };
        recordFeedback.mutate(feedbackData, {
          onError: () => {
            /* Non-blocking */
          },
        });
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
          <LearningStatus eventCount={eventCount} compact />
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
          <>
            <ContextInspector meta={contextMeta} />
            <GenerationDraft
              phase={phase}
              draftText={draftText}
              wordCount={wordCount}
              targetNum={targetNum}
              tokenUsage={tokenUsage}
              isAcceptPending={acceptMutation.isPending}
              isRejectPending={rejectMutation.isPending}
              onStop={handleStop}
              onAccept={() => {
                if (!originalTextRef.current) {
                  originalTextRef.current = draftText;
                }
                acceptMutation.mutate();
              }}
              onReject={() => {
                if (!originalTextRef.current) {
                  originalTextRef.current = draftText;
                }
                rejectMutation.mutate();
              }}
              onRegenerate={handleRegenerate}
            />
            {/* Rating prompt — shown after accept/reject action completes */}
            {showRating && (
              <RatingPrompt
                action={showRating}
                onSubmit={({ rating, reason }) => handleRatingDone(rating, reason)}
                onDismiss={() => handleRatingDone()}
              />
            )}
          </>
        )}

        {/* Error state */}
        {phase === "error" && (
          <div className="flex flex-col gap-3">
            <div className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm" role="alert">
              {errorMsg || t("generationPanel.unknownError")}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleRetry}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
              >
                <RotateCcw className="w-4 h-4" />
                <span>{t("aiActions.retry")}</span>
              </button>
              {errorMsg?.includes(t("generationPanel.contextTooLargeGeneric").slice(0, 10)) && (
                <button
                  type="button"
                  onClick={handleRetry}
                  className="flex items-center justify-center gap-2 px-3 py-2.5 border border-border rounded-lg text-sm text-foreground hover:bg-accent transition-colors"
                >
                  {t("generationPanel.contextInspectorAction")}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Connection lost banner */}
        {connectionLost && (
          <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-t border-border bg-yellow-500/10">
            <div className="flex items-center gap-2 text-sm text-yellow-700 dark:text-yellow-400">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{t("aiActions.connectionLost")}</span>
            </div>
            <button
              type="button"
              onClick={handleRetry}
              className="px-3 py-1 text-xs font-medium rounded-md bg-yellow-600 text-white hover:bg-yellow-700 transition-colors"
            >
              {t("aiActions.connectionLostRetry")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
