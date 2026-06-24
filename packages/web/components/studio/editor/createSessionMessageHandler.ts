"use client";

import type { SessionResponse } from "@/lib/api/writing-session-socket";
import type { Message } from "../editor/ChatMessage";
import { createMessageId } from "./sessionSocketMessages";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MessageHandlerCallbacks {
  readonly setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  readonly setStreamingText: (text: string) => void;
  readonly setIsStreaming: (streaming: boolean) => void;
  readonly setIsConnected: (connected: boolean) => void;
  readonly setSaveNotification: (notification: string | null) => void;
  readonly streamingTextRef: React.MutableRefObject<string>;
  readonly mode: "interactive_session" | "interview_assisted";
  readonly sessionEndedLabel: string;
  readonly errorConnectingLabel: string;
  readonly savedLabel: string;
  readonly generationStoppedLabel?: string;
  readonly recoveryFailedLabel?: string;
  readonly setRecoveryState?: (state: RecoveryState) => void;
  readonly setSessionId?: (sessionId: string) => void;
}

export type RecoveryState = "idle" | "reconnecting" | "recovered" | "failed";

function isTranscriptRole(value: unknown): value is Message["role"] {
  return value === "user" || value === "assistant" || value === "system";
}

function normalizeTranscriptTail(input: unknown): Message[] {
  if (!Array.isArray(input)) return [];

  return input.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const record = item as Record<string, unknown>;
    if (!isTranscriptRole(record.role)) return [];
    const content = typeof record.content === "string" ? record.content : "";
    const prose = typeof record.prose === "string" ? record.prose : undefined;

    return [{ id: createMessageId(), role: record.role, content, prose } satisfies Message];
  });
}

function notifyTemporarily(
  setSaveNotification: (notification: string | null) => void,
  label: string,
): void {
  setSaveNotification(label);
  setTimeout(() => setSaveNotification(null), 3000);
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/** Creates the message handler callback for WritingSessionSocket. */
export function createSessionMessageHandler({
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
  setSessionId,
}: MessageHandlerCallbacks) {
  return (msg: SessionResponse) => {
    switch (msg.type) {
      case "greeting":
        if (msg.session_id) setSessionId?.(msg.session_id);
        if (mode !== "interview_assisted") {
          setMessages((prev) => [
            ...prev,
            {
              id: createMessageId(),
              role: "assistant",
              content: msg.message ?? msg.text ?? "",
            },
          ]);
        }
        setIsConnected(true);
        break;
      case "interview_greeting":
        setIsConnected(true);
        break;
      case "text_chunk":
        streamingTextRef.current += msg.text ?? "";
        setStreamingText(streamingTextRef.current);
        setIsStreaming(true);
        break;
      case "text_done": {
        const prose = streamingTextRef.current;
        streamingTextRef.current = "";
        setStreamingText("");
        setIsStreaming(false);
        if (prose)
          setMessages((prev) => [
            ...prev,
            { id: createMessageId(), role: "assistant", content: "", prose },
          ]);
        break;
      }
      case "generation_stopped": {
        const prose = msg.partial_prose ?? streamingTextRef.current;
        streamingTextRef.current = "";
        setStreamingText("");
        setIsStreaming(false);
        if (prose) {
          setMessages((prev) => [
            ...prev,
            { id: createMessageId(), role: "assistant", content: "", prose },
          ]);
        }
        if (generationStoppedLabel) {
          notifyTemporarily(setSaveNotification, generationStoppedLabel);
        }
        break;
      }
      case "draft_done": {
        const prose = msg.text ?? "";
        if (prose)
          setMessages((prev) => [
            ...prev,
            { id: createMessageId(), role: "assistant", content: "", prose },
          ]);
        break;
      }
      case "feedback_acknowledged":
        setMessages((prev) => [
          ...prev,
          { id: createMessageId(), role: "assistant", content: msg.message ?? "" },
        ]);
        break;
      case "saved":
        notifyTemporarily(setSaveNotification, savedLabel);
        break;
      case "session_recovered": {
        if (msg.session_id) setSessionId?.(msg.session_id);
        const transcriptMessages = normalizeTranscriptTail(msg.transcript_tail);
        const partialProse = msg.partial_prose ?? "";
        streamingTextRef.current = msg.stream_status === "streaming" ? partialProse : "";
        setStreamingText(streamingTextRef.current);
        setIsStreaming(msg.stream_status === "streaming" && partialProse.length > 0);
        setMessages((prev) => [
          ...prev,
          ...transcriptMessages,
          ...(partialProse && msg.stream_status !== "streaming"
            ? [
                {
                  id: createMessageId(),
                  role: "assistant" as const,
                  content: "",
                  prose: partialProse,
                },
              ]
            : []),
        ]);
        setRecoveryState?.("recovered");
        setIsConnected(true);
        break;
      }
      case "recovery_failed":
        streamingTextRef.current = "";
        setStreamingText("");
        setIsStreaming(false);
        setRecoveryState?.("failed");
        setMessages((prev) => [
          ...prev,
          {
            id: createMessageId(),
            role: "system",
            content: msg.message ?? recoveryFailedLabel ?? errorConnectingLabel,
          },
        ]);
        setIsConnected(false);
        break;
      case "connection_lost":
        setRecoveryState?.("reconnecting");
        setIsConnected(false);
        break;
      case "timeout":
        setMessages((prev) => [
          ...prev,
          { id: createMessageId(), role: "system", content: msg.message ?? sessionEndedLabel },
        ]);
        setIsConnected(false);
        break;
      case "error":
        setMessages((prev) => [
          ...prev,
          {
            id: createMessageId(),
            role: "system",
            content: msg.message ?? errorConnectingLabel,
          },
        ]);
        break;
    }
  };
}
