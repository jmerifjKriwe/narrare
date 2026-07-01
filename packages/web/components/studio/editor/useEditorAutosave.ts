import { useEffect, useMemo, useRef } from "react";
import { writingApi } from "@/lib/api/generation";
import { useRecordFeedback } from "@/lib/hooks/useMemory";
import type { FeedbackRequest } from "@/types";
import type { AutosaveOptions } from "./extensions/Autosave";

interface UseEditorAutosaveParams {
  onAutosave?: (content: string) => Promise<void>;
  autosaveInterval?: number;
  novelId?: string;
  chapterId?: string;
}

/**
 * Builds the {@link Autosave} extension configuration for the editor.
 *
 * Owns a single responsibility: turn the host-supplied save callback +
 * interval into the memoized options object the Autosave extension consumes,
 * including the implicit-accept feedback hook that records accepted
 * AI-generated content on save.
 *
 * The save callback is held in a ref so the extension config stays referentially
 * stable across renders even when the parent passes a new function identity.
 */
export function useEditorAutosave({
  onAutosave,
  autosaveInterval,
  novelId,
  chapterId,
}: UseEditorAutosaveParams): Partial<AutosaveOptions> {
  const recordFeedback = useRecordFeedback(novelId ?? "");
  const saveFnRef = useRef(onAutosave ?? (async () => {}));

  useEffect(() => {
    saveFnRef.current = onAutosave ?? (async () => {});
  }, [onAutosave]);

  return useMemo<Partial<AutosaveOptions>>(
    () => ({
      interval: autosaveInterval ?? 30_000,
      saveFn: (value: string) => saveFnRef.current(value),
      enabled: !!onAutosave,
      onImplicitAccept: novelId
        ? (data: {
            requestId: string;
            source: string;
            originalText: string;
            action: "accept" | "modify";
            currentText?: string;
          }) => {
            const feedbackData: FeedbackRequest = {
              action: data.action,
              suggestion_id: data.requestId,
              intent: data.source,
              suggestion_text: data.originalText,
              modification: data.currentText ?? null,
              project_id: novelId,
              chapter_id: chapterId ?? null,
              mode: data.source,
            };
            recordFeedback.mutate(feedbackData, { onError: () => {} });
            writingApi.acceptDraft(data.requestId, data.currentText).catch(() => {});
          }
        : undefined,
    }),
    [autosaveInterval, novelId, chapterId, recordFeedback, onAutosave],
  );
}
