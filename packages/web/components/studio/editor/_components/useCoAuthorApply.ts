"use client";

import type { Dispatch, SetStateAction } from "react";
import { useCallback } from "react";
import type { ChangeDetail } from "@/lib/api/coauthor";

import { applyPartialChanges } from "./coauthor-apply";
import { allChangesAccepted } from "./coauthor-message-utils";
import type { CoAuthorPhase } from "./coauthor-styles";

// ---------------------------------------------------------------------------
// Params
// ---------------------------------------------------------------------------

interface UseCoAuthorApplyParams {
  readonly changes: ChangeDetail[];
  readonly acceptance: Record<string, boolean>;
  readonly streamedText: string;
  readonly requestId: string;
  readonly chapterId: string;
  readonly novelId: string;
  readonly selectionText: string;
  readonly onAccept: (revisedText: string) => void;
  readonly setPhase: Dispatch<SetStateAction<CoAuthorPhase>>;
  readonly setSubmitting: Dispatch<SetStateAction<boolean>>;
  readonly setErrorMsg: Dispatch<SetStateAction<string | null>>;
  readonly errorGeneric: string;
}

// ---------------------------------------------------------------------------
// Hook — memoized apply handler for co-author change review
// ---------------------------------------------------------------------------

export function useCoAuthorApply({
  changes,
  acceptance,
  streamedText,
  requestId,
  chapterId,
  novelId,
  selectionText,
  onAccept,
  setPhase,
  setSubmitting,
  setErrorMsg,
  errorGeneric,
}: UseCoAuthorApplyParams) {
  return useCallback(async () => {
    if (allChangesAccepted(changes, acceptance)) {
      onAccept(streamedText);
      setPhase("done");
      return;
    }
    setSubmitting(true);
    try {
      const content = await applyPartialChanges({
        changes,
        acceptance,
        chapterId,
        novelId,
        requestId,
        selectionText,
      });
      onAccept(content);
      setPhase("done");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : errorGeneric);
      setPhase("error");
    } finally {
      setSubmitting(false);
    }
  }, [
    changes,
    acceptance,
    streamedText,
    requestId,
    chapterId,
    novelId,
    selectionText,
    onAccept,
    setPhase,
    setSubmitting,
    setErrorMsg,
    errorGeneric,
  ]);
}
