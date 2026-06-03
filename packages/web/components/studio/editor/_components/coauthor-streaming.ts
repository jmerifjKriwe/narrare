import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import {
  type ChangeDetail,
  type CoAuthorFocus,
  type CoAuthorRevision,
  streamCoAuthor,
} from "@/lib/api/coauthor";
import { createAcceptanceMap } from "./coauthor-message-utils";
import type { CoAuthorPhase } from "./coauthor-styles";

// ---------------------------------------------------------------------------
// Streaming contract
// ---------------------------------------------------------------------------

interface StartCoAuthorStreamingParams {
  readonly novelId: string;
  readonly chapterId: string;
  readonly selectionText: string;
  readonly contextBefore?: string;
  readonly contextAfter?: string;
  readonly selectedFocus: readonly CoAuthorFocus[];
  readonly errorGeneric: string;
  readonly abortRef: MutableRefObject<AbortController | null>;
  readonly setPhase: Dispatch<SetStateAction<CoAuthorPhase>>;
  readonly setStreamedText: Dispatch<SetStateAction<string>>;
  readonly setChanges: Dispatch<SetStateAction<ChangeDetail[]>>;
  readonly setReasoning: Dispatch<SetStateAction<string>>;
  readonly setRequestId: Dispatch<SetStateAction<string>>;
  readonly setAcceptance: Dispatch<SetStateAction<Record<string, boolean>>>;
  readonly setErrorMsg: Dispatch<SetStateAction<string | null>>;
}

// ---------------------------------------------------------------------------
// Streaming lifecycle
// ---------------------------------------------------------------------------

export const startCoAuthorStreaming = ({
  novelId,
  chapterId,
  selectionText,
  contextBefore,
  contextAfter,
  selectedFocus,
  errorGeneric,
  abortRef,
  setPhase,
  setStreamedText,
  setChanges,
  setReasoning,
  setRequestId,
  setAcceptance,
  setErrorMsg,
}: StartCoAuthorStreamingParams): void => {
  setPhase("streaming");
  setStreamedText("");
  setChanges([]);
  setReasoning("");
  setErrorMsg(null);
  setRequestId(crypto.randomUUID());

  const controller = new AbortController();
  abortRef.current = controller;

  streamCoAuthor(
    chapterId,
    novelId,
    {
      selection_text: selectionText,
      context_before: contextBefore,
      context_after: contextAfter,
      focus: [...selectedFocus],
    },
    {
      onChunk: (text) => setStreamedText((prev) => prev + text),
      onComplete: (revision: CoAuthorRevision) => {
        setChanges(revision.changes);
        setReasoning(revision.reasoning);
        if (revision.request_id) setRequestId(revision.request_id);
        setAcceptance(createAcceptanceMap(revision.changes, true));
        setPhase(revision.changes.length > 0 ? "review" : "done");
        abortRef.current = null;
      },
      onError: (err) => {
        if (err.message.includes("Abort")) return;
        setErrorMsg(err.message || errorGeneric);
        setPhase("error");
        abortRef.current = null;
      },
    },
    controller.signal,
  );
};
