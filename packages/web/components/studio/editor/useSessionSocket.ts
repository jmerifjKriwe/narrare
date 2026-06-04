"use client";

/**
 * useSessionSocket — WebSocket lifecycle management for writing sessions.
 *
 * Handles connection, message parsing, and state updates.
 * Extracted from SessionPanel for RULE-04 compliance.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { WritingSessionSocket } from "@/lib/api/generation";
import type { Message } from "../editor/ChatMessage";
import { createSessionMessageHandler } from "./createSessionMessageHandler";

let messageCounter = 0;

export function createMessageId(): string {
  messageCounter += 1;
  return `msg-${messageCounter}`;
}

interface UseSessionSocketOptions {
  readonly chapterId: string;
  readonly novelId: string;
  readonly mode: "interactive_session" | "interview_assisted";
  readonly userId: string | undefined;
  readonly sessionEndedLabel: string;
  readonly errorConnectingLabel: string;
  readonly savedLabel: string;
}

export function useSessionSocket({
  chapterId,
  novelId,
  mode,
  userId,
  sessionEndedLabel,
  errorConnectingLabel,
  savedLabel,
}: UseSessionSocketOptions) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [saveNotification, setSaveNotification] = useState<string | null>(null);

  const socketRef = useRef<WritingSessionSocket | null>(null);
  const streamingTextRef = useRef("");

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
      }),
      () => setIsConnected(false),
      userId,
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
  }, [chapterId, userId, novelId, mode, sessionEndedLabel, errorConnectingLabel, savedLabel]);

  const sendMessage = useCallback(
    (
      type:
        | "user_direction"
        | "user_feedback"
        | "save_to_chapter"
        | "end_session"
        | "generate_draft",
      content?: string,
    ) => {
      if (!socketRef.current) return;
      if (type === "user_direction") {
        socketRef.current.send({ type, content });
      } else if (type === "save_to_chapter") {
        socketRef.current.send({ type, text: content });
      } else {
        socketRef.current.send({ type });
      }
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
    isConnected,
    isStreaming,
    setIsStreaming,
    setStreamingText,
    saveNotification,
    sendMessage,
    closeSocket,
  };
}
