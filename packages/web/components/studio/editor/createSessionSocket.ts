"use client";

/**
 * createSessionSocket — builds the WritingSessionSocket for a studio
 * editor session, wiring message handling and the recovery-state error
 * mapping. Extracted from useSessionSocket for RULE-04 compliance.
 */

import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import { authApi } from "@/lib/api/client";
import { WritingSessionSocket } from "@/lib/api/generation";
import type { Message } from "../editor/ChatMessage";
import { createSessionMessageHandler, type RecoveryState } from "./createSessionMessageHandler";

interface CreateSessionSocketParams {
  readonly chapterId: string;
  readonly novelId: string;
  readonly mode: "interactive_session" | "interview_assisted";
  readonly sessionEndedLabel: string;
  readonly errorConnectingLabel: string;
  readonly savedLabel: string;
  readonly generationStoppedLabel?: string;
  readonly recoveryFailedLabel?: string;
  readonly setMessages: Dispatch<SetStateAction<Message[]>>;
  readonly setStreamingText: (text: string) => void;
  readonly setIsStreaming: (streaming: boolean) => void;
  readonly setIsConnected: (connected: boolean) => void;
  readonly setSaveNotification: (notification: string | null) => void;
  readonly setRecoveryState: (state: RecoveryState) => void;
  readonly streamingTextRef: MutableRefObject<string>;
  readonly sessionIdRef: MutableRefObject<string | undefined>;
  /** True after a terminal ticket-mint failure (see the onError mapping). */
  readonly transportDeadRef: MutableRefObject<boolean>;
}

/** Creates the configured WritingSessionSocket for a writing session. */
export function createSessionSocket({
  chapterId,
  novelId,
  mode,
  sessionEndedLabel,
  errorConnectingLabel,
  savedLabel,
  generationStoppedLabel,
  recoveryFailedLabel,
  setMessages,
  setStreamingText,
  setIsStreaming,
  setIsConnected,
  setSaveNotification,
  setRecoveryState,
  streamingTextRef,
  sessionIdRef,
  transportDeadRef,
}: CreateSessionSocketParams): WritingSessionSocket {
  // Connection-evidence gate: a live socket clears any dead-end marker.
  const handleConnected = (connected: boolean) => {
    setIsConnected(connected);
    if (connected) transportDeadRef.current = false;
  };

  return new WritingSessionSocket(
    chapterId,
    createSessionMessageHandler({
      setMessages,
      setStreamingText,
      setIsStreaming,
      setIsConnected: handleConnected,
      setSaveNotification,
      streamingTextRef,
      mode,
      sessionEndedLabel,
      errorConnectingLabel,
      savedLabel,
      generationStoppedLabel,
      recoveryFailedLabel,
      setRecoveryState,
      setSessionId: (sessionId) => {
        sessionIdRef.current = sessionId;
      },
    }),
    (kind) => {
      setIsConnected(false);
      if (kind === "ticket_mint") {
        // The socket schedules no reconnect after a failed mint, so
        // "reconnecting" would promise a reconnection that never
        // happens. Surface the dead-end as "failed" — the banner branch
        // with the retry affordance.
        transportDeadRef.current = true;
        if (sessionIdRef.current) setRecoveryState("failed");
        return;
      }
      if (sessionIdRef.current) setRecoveryState("reconnecting");
    },
    // ADR-084: the socket fetches a fresh single-use ticket per connection
    // attempt; identity is derived server-side. The auth-readiness gate in
    // the hook is never transmitted.
    () => authApi.wsTicket().then((ticket) => ticket.token),
    novelId,
    mode,
  );
}
