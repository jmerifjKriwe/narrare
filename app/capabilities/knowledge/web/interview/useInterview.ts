/**
 * The interview's controller (W9 Task 10): the session read, its list, the
 * three writes, and each interview's own conversation state — the writer's
 * composer text, the last failed turn and the body its retry re-sends. The
 * component owns the chrome; this owns the conversation's state.
 *
 * That state is keyed by the session, not by what is shown: a turn sent in A
 * keeps its draft, its failure and its retry when the writer moves to B, and
 * a failure that lands while B is shown is there on return — nothing of one
 * interview ever shows in another. The writer's text is never cleared when a
 * turn starts — only when its own answer landed — so a failed turn keeps it
 * exactly as the wire's copy promises, and «Erneut versuchen» re-sends the
 * body that failed (the chips included: their label is the turn's text, not
 * what stands in the composer). A closed session answers 409 and a missing
 * one 404: the first becomes the ended face through the invalidation the
 * mutation settles with, the second hands the panel back to the chooser.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import type { AssistantTurnCreate } from "@shell/lib/api/client";
import type { ApiError } from "@shell/lib/api/errors";
import {
  useAssistantSessionQuery,
  useAssistantSessionsQuery,
  useAssistantTurn,
  useCloseAssistantSession,
  useOpenAssistantSession,
} from "@shell/lib/query";

import { interviewFace, isTurnFailure, type InterviewFailure } from "./interviewState";

/** One interview's conversation state: the draft the writer has typed, the
 *  last turn's named failure and the refused turn the retry re-sends — keyed
 *  by the session, so nothing of one interview shows in another and a failure
 *  that lands while another is shown is still there on return. */
interface InterviewSlot {
  text: string;
  failure: InterviewFailure | null;
  /** The refused turn's session beside its body, so a retry can never send
   *  one interview's text through another. */
  failed: { sessionId: string; body: AssistantTurnCreate } | null;
}

const EMPTY_SLOT: InterviewSlot = { text: "", failure: null, failed: null };

function slotOf(slots: Record<string, InterviewSlot>, id: string | null): InterviewSlot {
  return id === null ? EMPTY_SLOT : (slots[id] ?? EMPTY_SLOT);
}

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

  const [slots, setSlots] = useState<Record<string, InterviewSlot>>({});
  // The turns this controller sent, counted per session. TanStack Query's
  // mutation observer follows only the newest `mutate` call, so the hook's
  // `isPending`/`variables` cannot say whether the session now shown has an
  // answer out: sending in A and then in B would make A look idle and detach
  // A's own settle callbacks. The count is the controller's own, and every
  // turn settles on its own promise instead of on the observer.
  const [turnsInFlight, setTurnsInFlight] = useState<Record<string, number>>({});

  /** One interview's slot, replaced wholesale so React sees a new object. */
  const updateSlot = useCallback(
    (id: string, update: (slot: InterviewSlot) => InterviewSlot) => {
      setSlots((all) => ({ ...all, [id]: update(all[id] ?? EMPTY_SLOT) }));
    },
    [],
  );

  /** The interview now shown; the chooser has no slot to read. */
  const shown = slotOf(slots, sessionId);

  const setText = useCallback(
    (value: string) => {
      if (sessionId === null) return;
      updateSlot(sessionId, (slot) => ({ ...slot, text: value }));
    },
    [sessionId, updateSlot],
  );

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

  // A missing session goes back to the chooser, not to a dead panel — but only
  // once the panel is shown. The invalidating settle of the read's own family
  // may ask again meanwhile; the navigation clears the parameter, so the read
  // turns off with it.
  useEffect(() => {
    if (!visible) return;
    const error = session.error as ApiError | null;
    if (error?.status === 404 || error?.code === "not-found") onNotFound();
  }, [session.error, onNotFound, visible]);

  /** One turn settled: its session's count goes down, whether its answer
   *  landed or failed — and for the session it was sent for, never for the
   *  one shown. */
  const settleTurn = useCallback((sentFor: string) => {
    setTurnsInFlight((counts) => {
      const next = { ...counts };
      const left = (next[sentFor] ?? 1) - 1;
      if (left > 0) next[sentFor] = left;
      else delete next[sentFor];
      return next;
    });
  }, []);

  const send = useCallback(
    (body: AssistantTurnCreate) => {
      if (sessionId === null) return;
      const sentFor = sessionId;
      const chip = body.act !== undefined && body.act !== null;
      // Sending spends this interview's own failure; no other interview's.
      updateSlot(sentFor, (slot) => ({ ...slot, failure: null, failed: null }));
      setTurnsInFlight((counts) => ({ ...counts, [sentFor]: (counts[sentFor] ?? 0) + 1 }));
      // `mutateAsync`'s promise settles for THIS turn, whoever was sent after
      // it; the per-call callbacks of `mutate` would stop firing once the
      // hook's observer followed a later call. The catch takes the wire's
      // rejection, so no turn can escape as an unhandled rejection.
      void (async () => {
        try {
          await turn.mutateAsync({ sessionId: sentFor, body });
          // The answer landed in the interview it was sent for, whoever is
          // shown: its failure is spent, and a plain answer leaves its own
          // composer. A chip's label was never the composer's text.
          updateSlot(sentFor, (slot) => ({
            ...slot,
            failure: null,
            failed: null,
            text: chip ? slot.text : "",
          }));
        } catch (error) {
          const wire = error as ApiError;
          if (wire.code === "not-found") {
            // A missing session is the read's own 404: navigate only when it
            // is the interview now shown and the panel is visible, so a turn
            // never opens the chooser behind the writer's back.
            if (sentFor === sessionIdRef.current && visibleRef.current) onNotFound();
            return;
          }
          // A 409 means the session ended elsewhere: the settle refetch
          // brings `closed_at`, and the panel turns into its ended face.
          if (wire.code === "session-closed") return;
          // A 422 `suggestion-mismatch` is a validation refusal, not a
          // provider failure: retrying would send the same stale body. Its
          // own face sends the writer to the suggestion that stands now —
          // the settle refetch already brings it back into the transcript.
          if (wire.code === "suggestion-mismatch") {
            updateSlot(sentFor, (slot) => ({
              ...slot,
              failure: {
                code: "suggestion-mismatch",
                detail: typeof wire.detail === "string" ? wire.detail : undefined,
              },
              failed: null,
            }));
            return;
          }
          // A provider failure is this interview's too, whether or not it is
          // shown: the writer finds it, and its retry, on return.
          updateSlot(sentFor, (slot) => ({
            ...slot,
            failure: {
              code: isTurnFailure(wire.code ?? undefined)
                ? (wire.code as string)
                : "provider-error",
              detail: typeof wire.detail === "string" ? wire.detail : undefined,
              // An unknown code keeps its name beside the generic copy.
              cause: isTurnFailure(wire.code ?? undefined)
                ? undefined
                : (wire.code ?? undefined),
              chip,
            },
            failed: { sessionId: sentFor, body },
            // The failure face says the text is still in the composer. A
            // failed plain answer puts its own text back even when the writer
            // had switched away and the composer had been emptied; a chip's
            // label was never the composer's, so its failure says nothing
            // about the field.
            text: chip ? slot.text : body.text,
          }));
        } finally {
          settleTurn(sentFor);
        }
      })();
    },
    [onNotFound, sessionId, settleTurn, turn, updateSlot],
  );

  const sendText = useCallback(() => {
    if (shown.text.trim() === "") return;
    send({ text: shown.text });
  }, [send, shown.text]);

  const retry = useCallback(() => {
    // The refused body goes back to the interview it failed in — never to
    // whichever interview happens to be shown.
    const refused = shown.failed;
    if (refused === null || refused.sessionId !== sessionId) return;
    send(refused.body);
  }, [send, sessionId, shown.failed]);

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

  // The list's own rows; a failed background refresh keeps the last answer.
  const sessionRows = sessions.data ?? [];
  const turns = session.data?.turns ?? [];
  // Busy is the shown interview's own count of turns in flight — not the
  // mutation observer's, which only ever names the latest call. A close
  // belongs to the session it was sent for the same way: while another
  // interview is shown, A's close must not disable B's end button or report
  // its failure above it. The settle's invalidation still refreshes A's own
  // read, so A's truth is there when A is shown again.
  const pending = sessionId !== null && (turnsInFlight[sessionId] ?? 0) > 0;
  const closeIsHere = close.variables === sessionId;
  const face = interviewFace({
    session: session.data ?? null,
    turns,
    pending,
    failure: shown.failure,
  });

  return {
    /** The chooser draws only with no session; a session read in flight is its
     *  own loading face (`reading`), never a flash of the chooser. */
    face,
    reading: sessionId !== null && session.isPending,
    readFailed: session.isError,
    session: session.data ?? null,
    sessions: sessionRows,
    sessionsPending: sessions.isPending,
    /** Only a read that failed with nothing cached is the failure face: a
     *  failed background refresh keeps the rows already on screen (a stale
     *  list beats an empty one, and its counts stay true to what is shown). */
    sessionsFailed: sessions.isError && sessionRows.length === 0,
    /** The list's own read again; its answer restores counts and rows. */
    retrySessions: () => void sessions.refetch(),
    text: shown.text,
    setText,
    failure: shown.failure,
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
