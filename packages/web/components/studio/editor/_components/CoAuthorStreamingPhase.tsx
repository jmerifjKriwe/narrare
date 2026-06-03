"use client";

import { Loader2, X } from "lucide-react";
import { useTranslations } from "next-intl";

import { btnSecondary, wordCount } from "./coauthor-styles";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CoAuthorStreamingPhaseProps {
  readonly streamedText: string;
  readonly onStop: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CoAuthorStreamingPhase({ streamedText, onStop }: CoAuthorStreamingPhaseProps) {
  const t = useTranslations("studio");

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
        <Loader2 className="w-5 h-5 animate-spin text-primary" />
        <div>
          <p className="text-sm font-medium">{t("coAuthor.streaming")}</p>
          {streamedText.trim().length > 0 && (
            <p className="text-xs text-muted-foreground mt-1">
              {t("coAuthor.wordsReceived", { count: wordCount(streamedText) })}
            </p>
          )}
        </div>
      </div>
      {streamedText.trim().length > 0 && (
        <div className="p-3 rounded-lg border border-border bg-card text-sm leading-relaxed max-h-60 overflow-y-auto">
          {streamedText}
        </div>
      )}
      <button
        type="button"
        onClick={onStop}
        className={`${btnSecondary} flex items-center justify-center gap-2 w-full`}
      >
        <X className="w-4 h-4" />
        <span>{t("coAuthor.stop")}</span>
      </button>
    </div>
  );
}
