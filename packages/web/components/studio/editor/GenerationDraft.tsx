"use client";

import { RotateCcw, Sparkles, StopCircle } from "lucide-react";
import { useTranslations } from "next-intl";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GenerationDraftProps {
  readonly phase: "streaming" | "review";
  readonly draftText: string;
  readonly wordCount: number;
  readonly targetNum: number;
  readonly isAcceptPending: boolean;
  readonly isRejectPending: boolean;
  readonly onStop: () => void;
  readonly onAccept: () => void;
  readonly onReject: () => void;
  readonly onRegenerate: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GenerationDraft({
  phase,
  draftText,
  wordCount,
  targetNum,
  isAcceptPending,
  isRejectPending,
  onStop,
  onAccept,
  onReject,
  onRegenerate,
}: GenerationDraftProps) {
  const t = useTranslations("studio");

  const progressPct = Math.min(100, Math.round((wordCount / targetNum) * 100));

  return (
    <div className="flex flex-col gap-3 flex-1">
      {/* Badge + word count */}
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium">
          <Sparkles className="w-3 h-3" />
          {t("generationPanel.aiDraftBadge")}
        </span>
        <span className="text-xs text-muted-foreground">
          {t("generationPanel.wordCountProgress", {
            current: wordCount.toLocaleString(),
            target: targetNum.toLocaleString(),
          })}
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1.5 bg-accent rounded-full overflow-hidden">
        <div
          className="h-full bg-primary rounded-full transition-all duration-300"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {/* Draft text */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3 rounded-lg bg-muted/50 text-sm text-foreground whitespace-pre-wrap">
        {draftText || (
          <span className="text-muted-foreground italic">
            {t("generationPanel.waitingForText")}
          </span>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        {phase === "streaming" && (
          <button
            type="button"
            onClick={onStop}
            className="flex items-center gap-1.5 px-3 py-2 border border-border rounded-lg text-sm text-foreground hover:bg-accent transition-colors"
          >
            <StopCircle className="w-4 h-4" />
            <span>{t("generationPanel.stop")}</span>
          </button>
        )}
        {phase === "review" && (
          <>
            <button
              type="button"
              onClick={onAccept}
              disabled={isAcceptPending}
              className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {t("generationPanel.accept")}
            </button>
            <button
              type="button"
              onClick={onReject}
              disabled={isRejectPending}
              className="flex items-center gap-1.5 px-3 py-2 border border-border rounded-lg text-sm text-foreground hover:bg-accent transition-colors"
            >
              {t("generationPanel.reject")}
            </button>
            <button
              type="button"
              onClick={onRegenerate}
              className="flex items-center gap-1.5 px-3 py-2 border border-border rounded-lg text-sm text-foreground hover:bg-accent transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              <span>{t("generationPanel.regenerate")}</span>
            </button>
          </>
        )}
      </div>
    </div>
  );
}
