"use client";

import type { SessionResponse } from "@/lib/api/generation";
import type { Message } from "../editor/ChatMessage";
import { createMessageId } from "./useSessionSocket";

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
}: MessageHandlerCallbacks) {
  return (msg: SessionResponse) => {
    switch (msg.type) {
      case "greeting":
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
        setSaveNotification(savedLabel);
        setTimeout(() => setSaveNotification(null), 3000);
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
