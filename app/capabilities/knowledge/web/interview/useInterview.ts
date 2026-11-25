/**
 * The interview's controller (W9 Task 10): the session read, its list, the
 * three writes, the writer's composer text and the last failed turn. The
 * component owns the chrome; this owns the conversation's state.
 *
 * The writer's text is never cleared when a turn starts — only when its own
 * answer landed — so a failed turn keeps it exactly as the wire's copy
 * promises, and «Erneut versuchen» re-sends the body that failed (the chips
 * included: their label is the turn's text, not what stands in the composer).
 * A closed session answers 409 and a missing one 404: the first becomes the
 * ended face through the invalidation the mutation settles with, the second
 * hands the panel back to the chooser.
 */
import { useCallback, useEffect, useState } from "react";

import type { AssistantTurnCreate } from "@shell/lib/api/client";
import type { WireError } from "@shell/lib/query";
import {
  useAssistantSessionQuery,
  useAssistantSessionsQuery,
  useAssistantTurn,
  useCloseAssistantSession,
  useOpenAssistantSession,
} from "@shell/lib/query";

import { interviewFace, isTurnFailure, type InterviewFailure } from "./interviewState";

export function useInterview({
  novelId,
  sessionId,
  onOpened,
  onNotFound,
}: {
  novelId: string;
  /** Null is the chooser (`new`); a string reads that interview. */
  sessionId: string | null;
  onOpened: (id: string) => void;
  onNotFound: () => void;
}) {
  const sessions = useAssistantSessionsQuery(novelId);
  const session = useAssistantSessionQuery(sessionId);
  const open = useOpenAssistantSession();
  const turn = useAssistantTurn();
  const close = useCloseAssistantSession();

  const [text, setText] = useState("");
  const [failure, setFailure] = useState<InterviewFailure | null>(null);
  const [failedBody, setFailedBody] = useState<AssistantTurnCreate | null>(null);

  // A new session is a new conversation: no failure or text carries across.
  // (The panel is remounted per session anyway; this keeps a same-component
  // switch — a session row clicked from the list — equally clean.)
  // biome-ignore lint/correctness/useExhaustiveDependencies: sessionId is the deliberate reset trigger; the body only clears state.
  useEffect(() => {
    setFailure(null);
    setFailedBody(null);
    setText("");
  }, [sessionId]);

  // A missing session goes back to the chooser, not to a dead panel. The
  // invalidating settle of the read's own family may ask again meanwhile; the
  // navigation clears the parameter, so the read turns off with it.
  useEffect(() => {
    const error = session.error as WireError | null;
    if (error?.status === 404 || error?.code === "not-found") onNotFound();
  }, [session.error, onNotFound]);

  const send = useCallback(
    (body: AssistantTurnCreate) => {
      if (sessionId === null) return;
      setFailure(null);
      setFailedBody(null);
      turn.mutate(
        { sessionId, body },
        {
          onSuccess: () => {
            // Only the composer's own answer leaves the composer; a chip sends
            // its label, never what the writer had typed beside it.
            if (body.act === undefined || body.act === null) setText("");
          },
          onError: (error: WireError) => {
            if (error.code === "not-found") {
              onNotFound();
              return;
            }
            // A 409 means the session ended elsewhere: the settle refetch
            // brings `closed_at`, and the panel turns into its ended face.
            if (error.code === "session-closed") return;
            // A 422 `suggestion-mismatch` is a validation refusal, not a
            // provider failure: retrying would send the same stale body. Its
            // own face sends the writer to the suggestion that stands now —
            // the settle refetch already brings it back into the transcript.
            if (error.code === "suggestion-mismatch") {
              setFailure({ code: "suggestion-mismatch", detail: error.detail });
              return;
            }
            setFailure({
              code: isTurnFailure(error.code) ? (error.code as string) : "provider-error",
              detail: error.detail,
              // An unknown code keeps its name beside the generic copy.
              cause: isTurnFailure(error.code) ? undefined : error.code,
            });
            setFailedBody(body);
          },
        },
      );
    },
    [onNotFound, sessionId, turn],
  );

  const sendText = useCallback(() => {
    if (text.trim() === "") return;
    send({ text });
  }, [send, text]);

  const retry = useCallback(() => {
    if (failedBody !== null) send(failedBody);
  }, [failedBody, send]);

  const start = useCallback(
    (entityType: string) => {
      open.mutate(
        { novel_id: novelId, mode: "knowledge.entity", entity_type: entityType },
        { onSuccess: (opened) => onOpened(opened.id) },
      );
    },
    [novelId, onOpened, open],
  );

  const end = useCallback(() => {
    if (sessionId === null) return;
    // The chooser face already reads `open.isError`; the close failure is
    // read beside the footer and cleared when the writer asks again.
    close.reset();
    close.mutate(sessionId);
  }, [close, sessionId]);

  const turns = session.data?.turns ?? [];
  const face = interviewFace({
    session: session.data ?? null,
    turns,
    pending: turn.isPending,
    failure,
  });

  return {
    /** The chooser draws only with no session; a session read in flight is its
     *  own loading face (`reading`), never a flash of the chooser. */
    face,
    reading: sessionId !== null && session.isPending,
    readFailed: session.isError,
    session: session.data ?? null,
    sessions: sessions.data ?? [],
    sessionsPending: sessions.isPending,
    text,
    setText,
    failure,
    startFailed: open.isError,
    opening: open.isPending,
    send,
    sendText,
    retry,
    start,
    end,
    ending: close.isPending,
    endFailed: close.isError,
    retryRead: () => void session.refetch(),
  };
}
