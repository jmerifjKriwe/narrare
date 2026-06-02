"use client";

import type { Editor } from "@tiptap/react";
import { Check, Undo2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  acceptMark,
  getPendingModification,
  type PendingModification,
  rejectMark,
} from "@/components/studio/editor/extensions/AIAnnotation";
import { writingApi } from "@/lib/api/generation";
import { useRecordFeedback } from "@/lib/hooks/useMemory";
import type { FeedbackAction, FeedbackRequest } from "@/types";
import { RatingPrompt } from "./RatingPrompt";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AIAnnotationActionsProps {
  readonly editor: Editor;
  readonly projectId: string;
  readonly chapterId?: string;
}

/** Captured mark data used for feedback after the mark is removed. */
interface CapturedMarkData {
  requestId: string;
  source: string;
  originalText: string;
  currentText: string;
  wordCount: number;
  modification: PendingModification | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface PendingMarkInfo {
  requestId: string;
  source: string;
  wordCount: number;
  originalText: string;
  currentText: string;
}

function findPendingMarkInfo(editor: Editor): PendingMarkInfo | null {
  const markType = editor.state.schema.marks.aiGenerated;
  if (!markType) return null;

  let info: PendingMarkInfo | null = null;
  editor.state.doc.descendants((node, pos) => {
    if (info) return false;
    if (!node.isText) return;
    const mark = node.marks.find((m) => m.type === markType && m.attrs.status === "pending");
    if (mark) {
      const text = editor.state.doc.textBetween(pos, pos + node.nodeSize);
      info = {
        requestId: (mark.attrs.requestId as string) || "",
        source: (mark.attrs.source as string) || "extend",
        wordCount: text.split(/\s+/).filter(Boolean).length,
        originalText: (mark.attrs.originalText as string) || "",
        currentText: text,
      };
      return false;
    }
  });
  return info;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AIAnnotationActions({ editor, projectId, chapterId }: AIAnnotationActionsProps) {
  const t = useTranslations("studio");
  const recordFeedback = useRecordFeedback(projectId);

  const [markInfo, setMarkInfo] = useState<PendingMarkInfo | null>(null);
  const [showRating, setShowRating] = useState<"accept" | "reject" | null>(null);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const lastRequestIdRef = useRef<string>("");

  // Captured mark data for feedback — populated before mark removal
  const capturedRef = useRef<CapturedMarkData | null>(null);

  // Track pending mark changes
  useEffect(() => {
    const updateState = () => {
      const info = findPendingMarkInfo(editor);
      if (info) {
        setMarkInfo(info);
        lastRequestIdRef.current = info.requestId;
        // Hide rating when new mark appears
        setShowRating(null);
      } else if (!showRating) {
        setMarkInfo(null);
      }
    };

    updateState();
    editor.on("update", updateState);
    editor.on("transaction", updateState);
    return () => {
      editor.off("update", updateState);
      editor.off("transaction", updateState);
    };
  }, [editor, showRating]);

  // Position floating actions near the anchor decoration
  useEffect(() => {
    if (!markInfo) {
      setPosition(null);
      return;
    }

    const updatePosition = () => {
      const anchor = document.querySelector(".ai-annotation-anchor");
      if (!anchor) return;

      const anchorRect = anchor.getBoundingClientRect();
      const containerWidth = containerRef.current?.offsetWidth || 280;

      setPosition({
        top: anchorRect.bottom + 8,
        left: Math.max(
          8,
          Math.min(anchorRect.left - containerWidth / 2, window.innerWidth - containerWidth - 8),
        ),
      });
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    // Re-position on scroll within the editor
    const editorEl = editor.view.dom.closest(".overflow-y-auto, [class*=overflow]");
    if (editorEl) editorEl.addEventListener("scroll", updatePosition);

    return () => {
      window.removeEventListener("resize", updatePosition);
      if (editorEl) editorEl.removeEventListener("scroll", updatePosition);
    };
  }, [markInfo, editor]);

  // ---------------------------------------------------------------------------
  // Accept flow
  // ---------------------------------------------------------------------------

  const handleAccept = useCallback(() => {
    if (!markInfo) return;

    // Capture mark data BEFORE removing the mark
    const modification = getPendingModification(editor);
    const captured: CapturedMarkData = {
      requestId: markInfo.requestId,
      source: markInfo.source,
      originalText: markInfo.originalText,
      currentText: markInfo.currentText,
      wordCount: markInfo.wordCount,
      modification,
    };
    capturedRef.current = captured;

    // Remove the mark from the document (keep text)
    acceptMark(editor, null, markInfo.requestId);

    // Determine action: "modify" if user edited the AI text, otherwise "accept"
    const action: FeedbackAction = modification ? "modify" : "accept";

    // Notify backend — pass modified text if the user edited
    writingApi.acceptDraft(markInfo.requestId, modification?.current).catch(() => {
      /* Non-blocking — mark is already removed from document */
    });

    // Record feedback (without rating — rating comes later via RatingPrompt)
    const feedbackData: FeedbackRequest = {
      action,
      suggestion_id: markInfo.requestId,
      intent: markInfo.source,
      suggestion_text: markInfo.originalText || markInfo.currentText,
      modification: modification?.current ?? null,
      project_id: projectId,
      chapter_id: chapterId ?? null,
      mode: markInfo.source,
    };
    recordFeedback.mutate(feedbackData, {
      onError: () => {
        /* Non-blocking */
      },
    });

    setShowRating("accept");
  }, [markInfo, editor, projectId, chapterId, recordFeedback]);

  // ---------------------------------------------------------------------------
  // Reject flow
  // ---------------------------------------------------------------------------

  const handleReject = useCallback(() => {
    if (!markInfo) return;

    // Capture mark data BEFORE removing the mark + text
    const captured: CapturedMarkData = {
      requestId: markInfo.requestId,
      source: markInfo.source,
      originalText: markInfo.originalText,
      currentText: markInfo.currentText,
      wordCount: markInfo.wordCount,
      modification: null, // Rejection always uses action "reject"
    };
    capturedRef.current = captured;

    // Remove the marked text + mark from the document (undo transaction)
    rejectMark(editor, null, markInfo.requestId);

    // Notify backend
    writingApi.rejectDraft(markInfo.requestId).catch(() => {
      /* Non-blocking — text is already removed from document */
    });

    // Record feedback (without rating — rating comes later via RatingPrompt)
    const feedbackData: FeedbackRequest = {
      action: "reject",
      suggestion_id: markInfo.requestId,
      intent: markInfo.source,
      suggestion_text: markInfo.originalText || markInfo.currentText,
      project_id: projectId,
      chapter_id: chapterId ?? null,
      mode: markInfo.source,
    };
    recordFeedback.mutate(feedbackData, {
      onError: () => {
        /* Non-blocking */
      },
    });

    setShowRating("reject");
  }, [markInfo, editor, projectId, chapterId, recordFeedback]);

  // ---------------------------------------------------------------------------
  // Rating flow
  // ---------------------------------------------------------------------------

  const handleRatingSubmit = useCallback(
    (data: { rating: number; reason?: string }) => {
      const captured = capturedRef.current;
      if (!captured) {
        setShowRating(null);
        setMarkInfo(null);
        return;
      }

      // Record a follow-up feedback event with the rating
      const action: FeedbackAction =
        showRating === "accept" ? (captured.modification ? "modify" : "accept") : "reject";

      const feedbackData: FeedbackRequest = {
        action,
        suggestion_id: captured.requestId,
        intent: captured.source,
        suggestion_text: captured.originalText || captured.currentText,
        modification: captured.modification?.current ?? null,
        rating: data.rating,
        context: data.reason ? { reject_reason: data.reason } : undefined,
        project_id: projectId,
        chapter_id: chapterId ?? null,
        mode: captured.source,
      };
      recordFeedback.mutate(feedbackData, {
        onError: () => {
          /* Non-blocking */
        },
      });

      capturedRef.current = null;
      setShowRating(null);
      setMarkInfo(null);
    },
    [showRating, projectId, chapterId, recordFeedback],
  );

  const handleRatingDismiss = useCallback(() => {
    // User skipped rating — no additional feedback event needed
    capturedRef.current = null;
    setShowRating(null);
    setMarkInfo(null);
  }, []);

  // Don't render if no mark and no rating prompt
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
