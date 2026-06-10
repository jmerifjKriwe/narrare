"use client";

import { AlertTriangle, RotateCcw, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { LearningStatus } from "@/components/studio/learning/LearningStatus";
import { ContextInspector } from "./ContextInspector";
import { GenerationConfig } from "./GenerationConfig";
import { GenerationDraft } from "./GenerationDraft";
import { useGenerationPanelController } from "./generationPanelController";
import { RatingPrompt } from "./RatingPrompt";

interface GenerationPanelProps {
  readonly novelId: string;
  readonly chapterId: string;
  readonly chapterContent: string;
  readonly onDraftAccepted: (text: string) => void;
  readonly onClose: () => void;
  readonly onStartSession?: (mode: string) => void;
}

export function GenerationPanel({
  novelId,
  chapterId,
  chapterContent: _chapterContent,
  onDraftAccepted,
  onClose,
  onStartSession,
}: GenerationPanelProps) {
  const t = useTranslations("studio");
  const controller = useGenerationPanelController({ novelId, chapterId, onDraftAccepted, t });

  // Escape-Cancel Handler (KEYBOARD-001)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && controller.phase === "streaming") {
        e.preventDefault();
        controller.handleStop();
      }
      if (e.key === "Escape" && controller.phase === "review") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [controller.phase, controller.handleStop, onClose]);

  return (
    <div className="flex flex-col h-full border-l border-border bg-card w-80">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Sparkles className="w-4 h-4 text-primary" />
          <span>{t("generationPanel.title")}</span>
          <LearningStatus eventCount={controller.eventCount} compact />
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
        {controller.phase === "config" && (
          <GenerationConfig
            mode={controller.mode}
            setMode={controller.setMode}
            outline={controller.outline}
            setOutline={controller.setOutline}
            prompt={controller.prompt}
            setPrompt={controller.setPrompt}
            wordTarget={controller.wordTarget}
            setWordTarget={controller.setWordTarget}
            tone={controller.tone}
            setTone={controller.setTone}
            isPending={controller.isLoading}
            onGenerate={controller.handleGenerate}
            onStartSession={onStartSession}
          />
        )}

        {(controller.phase === "streaming" || controller.phase === "review") && (
          <>
            <ContextInspector meta={controller.contextMeta} />
            <GenerationDraft
              phase={controller.phase}
              draftText={controller.draftText}
              wordCount={controller.wordCount}
              targetNum={controller.targetNum}
              tokenUsage={controller.tokenUsage}
              isAcceptPending={controller.acceptMutation.isPending}
              isRejectPending={controller.rejectMutation.isPending}
              onStop={controller.handleStop}
              onAccept={controller.acceptDraft}
              onReject={controller.rejectDraft}
              onRegenerate={controller.handleRegenerate}
            />
            {controller.showRating && (
              <RatingPrompt
                action={controller.showRating}
                onSubmit={({ rating, reason }) => controller.handleRatingDone(rating, reason)}
                onDismiss={() => controller.handleRatingDone()}
              />
            )}
          </>
        )}

        {controller.phase === "error" && (
          <div className="flex flex-col gap-3">
            <div className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm" role="alert">
              {controller.errorMsg || t("generationPanel.unknownError")}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={controller.handleRetry}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
              >
                <RotateCcw className="w-4 h-4" />
                <span>{t("aiActions.retry")}</span>
              </button>
              {controller.errorMsg?.includes(
                t("generationPanel.contextTooLargeGeneric").slice(0, 10),
              ) && (
                <button
                  type="button"
                  onClick={controller.handleRetry}
                  className="flex items-center justify-center gap-2 px-3 py-2.5 border border-border rounded-lg text-sm text-foreground hover:bg-accent transition-colors"
                >
                  {t("generationPanel.contextInspectorAction")}
                </button>
              )}
            </div>
          </div>
        )}

        {controller.connectionLost && (
          <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-t border-border bg-yellow-500/10">
            <div className="flex items-center gap-2 text-sm text-yellow-700 dark:text-yellow-400">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{t("aiActions.connectionLost")}</span>
            </div>
            <button
              type="button"
              onClick={controller.handleRetry}
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
