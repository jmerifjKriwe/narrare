"use client";

/**
 * SessionActions — Action bar at the bottom of the writing session panel.
 *
 * Shows contextual actions: Generate Draft (interview mode),
 * Save to Chapter, Stop Generation (when streaming), and End Session.
 * Uses studio.aiActions.* labels (§16.4).
 */

import { Save, Send, Sparkles, StopCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import type { KeyboardEvent } from "react";

interface SessionActionsProps {
  readonly mode: "interactive_session" | "interview_assisted";
  readonly isConnected: boolean;
  readonly isStreaming: boolean;
  readonly hasAddedAny: boolean;
  readonly messageCount: number;
  readonly input: string;
  readonly onInputChange: (value: string) => void;
  readonly onSend: () => void;
  readonly onStopGeneration: () => void;
  readonly onGenerateDraft: () => void;
  readonly onSaveToChapter: () => void;
  readonly onEndSession: () => void;
}

export function SessionActions({
  mode,
  isConnected,
  isStreaming,
  hasAddedAny,
  messageCount,
  input,
  onInputChange,
  onSend,
  onStopGeneration,
  onGenerateDraft,
  onSaveToChapter,
  onEndSession,
}: SessionActionsProps) {
  const t = useTranslations("studio");
  const tAction = useTranslations("studio.aiActions");

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <>
      {/* Input area */}
      <div className="border-t border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("sessionPanel.inputPlaceholder")}
            disabled={!isConnected}
            className="flex-1 px-3 py-2 border border-border rounded-lg bg-background text-foreground text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/20 disabled:opacity-50"
          />
          <button
            type="button"
            onClick={onSend}
            disabled={!input.trim() || !isConnected}
            className="p-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label={t("sessionPanel.send")}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Action buttons */}
      <div className="border-t border-border px-4 py-3 flex gap-2">
        {/* Stop Generation — only when streaming */}
        {isStreaming && (
          <button
            type="button"
            onClick={onStopGeneration}
            className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/30 transition-colors"
          >
            <StopCircle className="w-4 h-4" />
            <span>{tAction("stop")}</span>
          </button>
        )}

        {mode === "interview_assisted" && messageCount >= 3 && !isStreaming && (
          <button
            type="button"
            onClick={onGenerateDraft}
            disabled={!isConnected}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-colors disabled:opacity-50"
          >
            <Sparkles className="w-4 h-4" />
            <span>{t("sessionPanel.generateDraft")}</span>
          </button>
        )}
        <button
          type="button"
          onClick={onSaveToChapter}
          disabled={!hasAddedAny || !isConnected}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-border rounded-lg text-sm text-foreground hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Save className="w-4 h-4" />
          <span>{t("sessionPanel.saveToChapter")}</span>
        </button>
        <button
          type="button"
          onClick={onEndSession}
          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm text-destructive hover:bg-destructive/10 transition-colors"
        >
          <span>{t("sessionPanel.endSession")}</span>
        </button>
      </div>
    </>
  );
}
