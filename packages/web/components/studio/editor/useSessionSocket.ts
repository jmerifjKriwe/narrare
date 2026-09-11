"use client";

/**
 * useSessionSocket — WebSocket lifecycle management for writing sessions.
 *
 * Handles connection, message parsing, and state updates.
 * Extracted from SessionPanel for RULE-04 compliance.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { WritingSessionSocket } from "@/lib/api/generation";
import type { Message } from "../editor/ChatMessage";
import type { RecoveryState } from "./createSessionMessageHandler";
import { createSessionSocket } from "./createSessionSocket";
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
  // True after a terminal ticket-mint failure: no socket exists and none is
  // scheduled (single-shot per connect(), ADR-084), so sends must
  // re-establish the connection instead of writing into the dead socket.
  const transportDeadRef = useRef(false);

  useEffect(() => {
    if (!userId) return;

    // A fresh socket invalidates any dead-end marker from a previous run.
    transportDeadRef.current = false;

    const socket = createSessionSocket({
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
    });

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
      if (transportDeadRef.current) {
        // After a terminal mint failure there is no socket to carry this
        // message (the banner retry lands here): re-establish the
        // connection — connect() mints a FRESH ticket and replays a pending
        // recover_session automatically once the socket opens.
        transportDeadRef.current = false;
        socketRef.current.connect();
        return true;
      }
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
