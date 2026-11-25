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
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

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
  visible = true,
  onOpened,
  onNotFound,
}: {
  novelId: string;
  /** Null is the chooser (`new`); a string reads that interview. */
  sessionId: string | null;
  /** False while the panel is hidden: the session read keeps following a
   *  running turn, but a 404 waits for the panel to be shown again instead of
   *  taking the writer to the chooser behind their back. */
  visible?: boolean;
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

  // The turn's callbacks are fixed when it starts, so they read the panel's
  // visibility and the session it was sent for through refs: a failure that
  // lands after the panel was hidden must not open the chooser behind the
  // writer's back, and a turn of the interview the writer left must not touch
  // the one now shown. Both are written in a LAYOUT effect, so no settle can
  // land between a hide's commit and a passive effect still reading `true`.
  const visibleRef = useRef(visible);
  const sessionIdRef = useRef(sessionId);
  useLayoutEffect(() => {
    const wasHidden = !visibleRef.current;
    visibleRef.current = visible;
    sessionIdRef.current = sessionId;
    // Showing the panel asks its session read again. The host keeps the read
    // subscribed for the page's lifetime, so without this ask an interview
    // ended in another tab while the panel was hidden would look open until a
    // turn settles or the window regains focus — a remount used to ask. The
    // chooser has no session to read.
    if (visible && wasHidden && sessionId !== null) void session.refetch();
  }, [visible, sessionId, session.refetch]);

  // A new session is a new conversation: no failure or text carries across.
  // (The panel is remounted per session anyway; this keeps a same-component
  // switch — a session row clicked from the list — equally clean.)
  // biome-ignore lint/correctness/useExhaustiveDependencies: sessionId is the deliberate reset trigger; the body only clears state.
  useEffect(() => {
    setFailure(null);
    setFailedBody(null);
    setText("");
  }, [sessionId]);

  // A missing session goes back to the chooser, not to a dead panel — but only
  // once the panel is shown. The invalidating settle of the read's own family
  // may ask again meanwhile; the navigation clears the parameter, so the read
  // turns off with it.
  useEffect(() => {
    if (!visible) return;
    const error = session.error as WireError | null;
    if (error?.status === 404 || error?.code === "not-found") onNotFound();
  }, [session.error, onNotFound, visible]);

  const send = useCallback(
    (body: AssistantTurnCreate) => {
      if (sessionId === null) return;
      setFailure(null);
      setFailedBody(null);
      turn.mutate(
        { sessionId, body },
        {
          onSuccess: (_data, variables) => {
            // A turn belongs to the session it was sent for: when the writer
            // has moved on, A's answer changes nothing in B.
            if (variables.sessionId !== sessionIdRef.current) return;
            // Only the composer's own answer leaves the composer; a chip sends
            // its label, never what the writer had typed beside it.
            if (body.act === undefined || body.act === null) setText("");
          },
          onError: (error: WireError, variables) => {
            // The same scope for the failure: A's error face, A's failed body
            // and A's eventual retry stay out of B's conversation.
            if (variables.sessionId !== sessionIdRef.current) return;
            if (error.code === "not-found") {
              // A hidden turn's missing session is the read's own 404: the
              // settle refetch finds it, and that effect waits for the panel
              // to be shown rather than opening it behind the writer's back.
              if (visibleRef.current) onNotFound();
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
  // A turn or a close belongs to the session it was sent for: while another
  // interview is shown, A's in-flight turn must not draw B's thinking row or
  // keep B's composer closed, and A's close must not disable B's end button
  // or report its failure above it. The settle's invalidation still refreshes
  // A's own read, so A's truth is there when A is shown again.
  const turnIsHere = turn.variables?.sessionId === sessionId;
  const closeIsHere = close.variables === sessionId;
  const face = interviewFace({
    session: session.data ?? null,
    turns,
    pending: turn.isPending && turnIsHere,
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
    ending: close.isPending && closeIsHere,
    endFailed: close.isError && closeIsHere,
    retryRead: () => void session.refetch(),
  };
}
