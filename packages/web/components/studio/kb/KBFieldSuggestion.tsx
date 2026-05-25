"use client";

/**
 * KB Field Suggestion — Live AI suggestion display with SSE streaming.
 *
 * Shows loading/streaming state with typing animation, then displays
 * the suggestion with reasoning and accept/reject buttons.
 */

import { Check, RotateCcw, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import type { KBCreationField, KBSuggestionResult } from "@/lib/api/kb-sessions";

interface KBFieldSuggestionProps {
  field: KBCreationField;
  isLoading?: boolean;
  streamedText?: string;
  result?: KBSuggestionResult | null;
  error?: Error | null;
  onAccept: (value: string) => void;
  onReject: () => void;
  onRetry: () => void;
}

export function KBFieldSuggestion({
  field,
  isLoading = false,
  streamedText = "",
  result = null,
  error = null,
  onAccept,
  onReject,
  onRetry,
}: KBFieldSuggestionProps) {
  const t = useTranslations("studio");
  const [displayText, setDisplayText] = useState("");

  // Typing animation effect for streamed text
  useEffect(() => {
    if (isLoading && streamedText.length > displayText.length) {
      const nextChar = streamedText[displayText.length];
      const timer = setTimeout(() => {
        setDisplayText((prev) => prev + nextChar);
      }, 15); // ~60 chars per second
      return () => clearTimeout(timer);
    }
    if (!isLoading && result) {
      setDisplayText(result.suggestion);
    }
  }, [displayText, isLoading, result, streamedText]);

  // Reset when field changes
  const prevFieldKeyRef = useRef(field.field_key);
  useEffect(() => {
    if (prevFieldKeyRef.current !== field.field_key) {
      setDisplayText("");
      prevFieldKeyRef.current = field.field_key;
    }
  }, [field.field_key]);

  // --- Idle state ---
  if (!isLoading && !result && !error) {
    return null;
  }

  // --- Error state ---
  if (error) {
    return (
      <div className="mt-3 p-4 border border-red-200 dark:border-red-900/50 rounded-lg bg-red-50 dark:bg-red-950/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
            <X className="w-4 h-4" />
            <span>{error.message || "Suggestion failed"}</span>
          </div>
          <button
            type="button"
            onClick={onRetry}
            className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300"
          >
            <RotateCcw className="w-3 h-3" />
            {t("kb.retry")}
          </button>
        </div>
      </div>
    );
  }

  // --- Loading / Streaming state ---
  if (isLoading) {
    return (
      <div className="mt-3 p-4 border border-border rounded-lg bg-muted/30">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          <span className="text-sm text-muted-foreground">{t("kb.aiSuggestion")}</span>
        </div>
        <div className="text-sm whitespace-pre-wrap min-h-[60px]">
          {displayText || (
            <span className="text-muted-foreground italic">{t("kb.aiThinking")}</span>
          )}
          {displayText.length > 0 && (
            <span className="inline-block w-0.5 h-4 bg-primary animate-pulse ml-0.5" />
          )}
        </div>
      </div>
    );
  }

  // --- Complete state (with result) ---
  if (result) {
    return (
      <div className="mt-3 p-4 border border-green-200 dark:border-green-900/50 rounded-lg bg-green-50 dark:bg-green-950/20">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-green-700 dark:text-green-400">
            {t("kb.aiSuggestion")}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onReject}
              className="flex items-center gap-1 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors"
            >
              <X className="w-3 h-3" />
              {t("kb.reject")}
            </button>
            <button
              type="button"
              onClick={() => onAccept(result.suggestion)}
              className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
            >
              <Check className="w-3 h-3" />
              {t("kb.accept")}
            </button>
          </div>
        </div>

        {/* Suggestion */}
        <div className="text-sm whitespace-pre-wrap mb-3">{result.suggestion}</div>

        {/* Reasoning */}
        {result.reasoning && (
          <div className="mt-2 pt-3 border-t border-green-200 dark:border-green-900/30">
            <div className="text-xs text-muted-foreground mb-1">{t("kb.aiReasoning")}</div>
            <div className="text-xs text-muted-foreground italic">{result.reasoning}</div>
          </div>
        )}
      </div>
    );
  }

  return null;
}
