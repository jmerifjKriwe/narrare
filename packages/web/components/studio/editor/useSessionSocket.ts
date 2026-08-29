"use client";

/**
 * useSessionSocket — WebSocket lifecycle management for writing sessions.
 *
 * Handles connection, message parsing, and state updates.
 * Extracted from SessionPanel for RULE-04 compliance.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { authApi } from "@/lib/api/client";
import { WritingSessionSocket } from "@/lib/api/generation";
import type { Message } from "../editor/ChatMessage";
import { createSessionMessageHandler, type RecoveryState } from "./createSessionMessageHandler";
import {
  buildSessionClientMessage,
  type SendMessageOptions,
  type SessionClientMessageType,
} from "./sessionSocketMessages";

interface UseSessionSocketOptions {
  readonly chapterId: string;
  readonly novelId: string;
  readonly mode: "interactive_session" | "interview_assisted";
  readonly userId: string | undefined;
  readonly sessionEndedLabel: string;
  readonly errorConnectingLabel: string;
  readonly savedLabel: string;
  readonly generationStoppedLabel?: string;
  readonly recoveryFailedLabel?: string;
}

export function useSessionSocket({
  chapterId,
  novelId,
  mode,
  userId,
  sessionEndedLabel,
  errorConnectingLabel,
  savedLabel,
  generationStoppedLabel,
  recoveryFailedLabel,
}: UseSessionSocketOptions) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [saveNotification, setSaveNotification] = useState<string | null>(null);
  const [recoveryState, setRecoveryState] = useState<RecoveryState>("idle");

  const socketRef = useRef<WritingSessionSocket | null>(null);
  const streamingTextRef = useRef("");
  const sessionIdRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!userId) return;

    const socket = new WritingSessionSocket(
      chapterId,
      createSessionMessageHandler({
        setMessages,
        setStreamingText,
        setIsStreaming,
        setIsConnected,
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
      () => {
        setIsConnected(false);
        if (sessionIdRef.current) setRecoveryState("reconnecting");
      },
      // ADR-084: the socket fetches a fresh single-use ticket per connection
      // attempt; identity is derived server-side. `userId` above is only the
      // auth-readiness gate and is never transmitted.
      () => authApi.wsTicket().then((ticket) => ticket.token),
      novelId,
      mode,
    );

    socketRef.current = socket;
    socket.connect();
    setIsConnected(true);

    return () => {
      socket.close();
      socketRef.current = null;
      setIsConnected(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    chapterId,
    userId,
    novelId,
    mode,
    sessionEndedLabel,
    errorConnectingLabel,
    savedLabel,
    generationStoppedLabel,
    recoveryFailedLabel,
  ]);

  const sendMessage = useCallback(
    (type: SessionClientMessageType, content?: string, options?: SendMessageOptions): boolean => {
      if (!socketRef.current) return false;
      const message = buildSessionClientMessage(type, content, options, sessionIdRef.current);
      if (!message) return false;
      socketRef.current.send(message);
      return true;
    },
    [],
  );

  const closeSocket = useCallback(() => {
    socketRef.current?.send({ type: "end_session" });
    socketRef.current?.close();
    socketRef.current = null;
    setIsConnected(false);
  }, []);

  return {
    messages,
    setMessages,
    streamingText,
    streamingTextRef,
    sessionIdRef,
    isConnected,
    isStreaming,
    setIsStreaming,
    setStreamingText,
    saveNotification,
    recoveryState,
    setRecoveryState,
    sendMessage,
    closeSocket,
  };
}
