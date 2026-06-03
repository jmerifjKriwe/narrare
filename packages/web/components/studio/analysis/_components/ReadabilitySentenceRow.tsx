"use client";

/**
 * ReadabilitySentenceRow — expandable row for a single sentence analysis.
 *
 * Shows the sentence text with a readability score badge. When expanded,
 * displays issues and an optional suggestions list.
 * Requires "use client" because it manages local expand/collapse state.
 */

import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

import type { SentenceAnalysis } from "@/lib/api/analysis";

interface SentenceRowProps {
  sentence: SentenceAnalysis;
  t: (key: string, params?: Record<string, unknown>) => string;
}

export function ReadabilitySentenceRow({ sentence, t }: SentenceRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const scorePercent = Math.round(sentence.readability_score * 100);
  const scoreColor =
    sentence.readability_score >= 0.7
      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
      : sentence.readability_score >= 0.4
        ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
        : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";

  return (
    <div className="rounded border border-border p-3">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-left"
        aria-expanded={expanded}
      >
        <span className="text-xs text-muted-foreground flex items-center gap-1.5 min-w-0 flex-1">
          <span className={`text-xs font-medium px-1.5 py-0.5 rounded flex-shrink-0 ${scoreColor}`}>
            {scorePercent}%
          </span>
          <span className="truncate">{sentence.sentence}</span>
        </span>
        <span className="text-xs text-muted-foreground flex-shrink-0 ml-2">
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </span>
      </button>
      {expanded && (
        <div className="mt-2 space-y-2 text-xs">
          {/* Issues list */}
          {sentence.issues.length > 0 && (
            <div className="space-y-1">
              {sentence.issues.map((issue) => (
                <div
                  key={`issue-${sentence.sentence_index}-${issue}`}
                  className="flex items-start gap-1.5 text-muted-foreground"
                >
                  <span className="mt-1 w-1 h-1 rounded-full bg-yellow-500 flex-shrink-0" />
                  <span>{issue}</span>
                </div>
              ))}
            </div>
          )}
          {/* Suggestions toggle */}
          {sentence.suggestions.length > 0 && (
            <div>
              <button
                type="button"
                onClick={() => setShowSuggestions(!showSuggestions)}
                className="text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300 font-medium flex items-center gap-1"
              >
                {showSuggestions ? (
                  <ChevronUp className="w-3 h-3" />
                ) : (
                  <ChevronDown className="w-3 h-3" />
                )}
                {t("readability.suggestions")} ({sentence.suggestions.length})
              </button>
              {showSuggestions && (
                <div className="mt-1.5 space-y-1.5">
                  {sentence.suggestions.map((suggestion) => (
                    <div
                      key={`suggestion-${sentence.sentence_index}-${suggestion.slice(0, 30)}`}
                      className="rounded bg-muted/50 p-2 text-muted-foreground italic"
                    >
                      {suggestion}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
