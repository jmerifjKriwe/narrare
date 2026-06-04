"use client";

import type { Editor } from "@tiptap/react";
import { Check, Undo2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { RatingPrompt } from "./RatingPrompt";
import { type CapturedMarkData, useAnnotationActions } from "./useAnnotationActions";
import { useAnnotationMarkTracker } from "./useAnnotationMarkTracker";
import { useAnnotationRating } from "./useAnnotationRating";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AIAnnotationActionsProps {
  readonly editor: Editor;
  readonly projectId: string;
  readonly chapterId?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AIAnnotationActions({ editor, projectId, chapterId }: AIAnnotationActionsProps) {
  const t = useTranslations("studio");
  const [showRating, setShowRating] = useState<"accept" | "reject" | null>(null);
  const capturedRef = useRef<CapturedMarkData | null>(null);

  const { markInfo, setMarkInfo, position, containerRef } = useAnnotationMarkTracker({
    editor,
    showRating,
    setShowRating,
  });

  const { handleAccept, handleReject } = useAnnotationActions({
    editor,
    projectId,
    chapterId,
    markInfo,
    setShowRating,
    capturedRef,
  });

  const { handleRatingSubmit, handleRatingDismiss } = useAnnotationRating({
    projectId,
    chapterId,
    showRating,
    setShowRating,
    setMarkInfo,
    capturedRef,
  });

  if (!markInfo && !showRating) return null;

  const sourceKey =
    markInfo?.source === "extend"
      ? "annotation.aiContinuation"
      : markInfo?.source === "rewrite"
        ? "annotation.aiRewrite"
        : "annotation.aiSuggestion";

  return (
    <div
      ref={containerRef}
      className="fixed z-50 w-72"
      style={position ? { top: position.top, left: position.left } : { display: "none" }}
    >
      {showRating ? (
        <RatingPrompt
          action={showRating}
          onSubmit={handleRatingSubmit}
          onDismiss={handleRatingDismiss}
        />
      ) : (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-card shadow-lg">
          <span className="text-xs font-medium text-muted-foreground flex-1">
            {t(sourceKey)} · {t("annotation.aiWords", { count: markInfo?.wordCount ?? 0 })}
          </span>
          <button
            type="button"
            onClick={handleAccept}
            className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
            aria-label={t("aiActions.accept")}
          >
            <Check className="w-3 h-3" />
            <span>{t("aiActions.accept")}</span>
          </button>
          <button
            type="button"
            onClick={handleReject}
            className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md border border-border hover:bg-accent transition-colors"
            aria-label={t("aiActions.reject")}
          >
            <Undo2 className="w-3 h-3" />
            <span>{t("aiActions.reject")}</span>
          </button>
        </div>
      )}
    </div>
  );
}
