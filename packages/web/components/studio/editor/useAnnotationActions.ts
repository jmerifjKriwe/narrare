"use client";

import type { Editor } from "@tiptap/react";
import { type MutableRefObject, useCallback } from "react";
import {
  acceptMark,
  getPendingModification,
  type PendingModification,
  rejectMark,
} from "@/components/studio/editor/extensions/AIAnnotation";
import { writingApi } from "@/lib/api/generation";
import { useRecordFeedback } from "@/lib/hooks/useMemory";
import type { FeedbackAction, FeedbackRequest } from "@/types";
import type { PendingMarkInfo } from "./useAnnotationMarkTracker";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Captured mark data used for feedback after the mark is removed. */
export interface CapturedMarkData {
  requestId: string;
  source: string;
  originalText: string;
  currentText: string;
  wordCount: number;
  modification: PendingModification | null;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

interface UseAnnotationActionsOptions {
  readonly editor: Editor;
  readonly projectId: string;
  readonly chapterId?: string;
  readonly markInfo: PendingMarkInfo | null;
  readonly setShowRating: (rating: "accept" | "reject" | null) => void;
  readonly capturedRef: MutableRefObject<CapturedMarkData | null>;
}

/** Handles accept/reject actions for AI annotation marks. */
export function useAnnotationActions({
  editor,
  projectId,
  chapterId,
  markInfo,
  setShowRating,
  capturedRef,
}: UseAnnotationActionsOptions) {
  const recordFeedback = useRecordFeedback(projectId);

  const handleAccept = useCallback(() => {
    if (!markInfo) return;

    // Capture mark data BEFORE removing the mark
    const modification = getPendingModification(editor);
    capturedRef.current = {
      requestId: markInfo.requestId,
      source: markInfo.source,
      originalText: markInfo.originalText,
      currentText: markInfo.currentText,
      wordCount: markInfo.wordCount,
      modification,
    };

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
  }, [markInfo, editor, projectId, chapterId, recordFeedback, setShowRating, capturedRef]);

  const handleReject = useCallback(() => {
    if (!markInfo) return;

    // Capture mark data BEFORE removing the mark + text
    capturedRef.current = {
      requestId: markInfo.requestId,
      source: markInfo.source,
      originalText: markInfo.originalText,
      currentText: markInfo.currentText,
      wordCount: markInfo.wordCount,
      modification: null, // Rejection always uses action "reject"
    };

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
  }, [markInfo, editor, projectId, chapterId, recordFeedback, setShowRating, capturedRef]);

  return { handleAccept, handleReject };
}
