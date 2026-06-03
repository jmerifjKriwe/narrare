"use client";

/**
 * SentimentSentenceRow — expandable row showing per-sentence sentiment details.
 *
 * Displays dominant emotion badge, VAD scores, word count, and dialogue flag.
 */

import { useState } from "react";

import type { SentenceSentiment } from "@/lib/api/analysis";

interface SentenceRowProps {
  sentence: SentenceSentiment;
  t: (key: string, params?: Record<string, unknown>) => string;
}

export function SentenceRow({ sentence, t }: SentenceRowProps) {
  const [expanded, setExpanded] = useState(false);
  const emotionLabel = sentence.dominant_emotion ?? t("sentiment.noDominantEmotion");

  return (
    <div className="rounded border border-border p-3">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-left"
        aria-expanded={expanded}
      >
        <span className="text-xs text-muted-foreground flex items-center gap-1.5 min-w-0 flex-1">
          <span className="text-xs font-medium bg-muted px-1.5 py-0.5 rounded flex-shrink-0">
            {emotionLabel}
          </span>
          <span className="truncate">{sentence.sentence}</span>
        </span>
        <span className="text-xs text-muted-foreground flex-shrink-0 ml-2">
          {expanded ? "▲" : "▼"}
        </span>
      </button>
      {expanded && (
        <div className="mt-2 space-y-1 text-xs text-muted-foreground">
          <div className="flex gap-4">
            <span>
              {t("sentiment.vad.valenceShort")} {sentence.vad.valence.toFixed(2)}{" "}
              {t("sentiment.vad.arousalShort")} {sentence.vad.arousal.toFixed(2)}{" "}
              {t("sentiment.vad.dominanceShort")} {sentence.vad.dominance.toFixed(2)}
            </span>
            {sentence.is_dialogue && <span className="italic">{t("sentiment.dialogue")}</span>}
          </div>
          <span>{t("sentiment.wordCount", { count: sentence.word_count })}</span>
        </div>
      )}
    </div>
  );
}
