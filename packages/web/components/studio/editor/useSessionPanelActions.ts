"use client";

import { type Dispatch, type MutableRefObject, type SetStateAction, useCallback } from "react";
import type { Message } from "./ChatMessage";
import type { SendMessageOptions, SessionClientMessageType } from "./sessionSocketMessages";

interface UseSessionPanelActionsOptions {
  readonly input: string;
  readonly proseBuffer: string;
  readonly sendMessage: (
    type: SessionClientMessageType,
    content?: string,
    options?: SendMessageOptions,
  ) => boolean;
  readonly closeSocket: () => void;
  readonly onClose: () => void;
  readonly setInput: (value: string) => void;
  readonly setMessages: Dispatch<SetStateAction<Message[]>>;
  readonly setAddedIds: Dispatch<SetStateAction<Set<string>>>;
  readonly setProseBuffer: Dispatch<SetStateAction<string>>;
  readonly setStreamingText: (text: string) => void;
  readonly setIsStreaming: (streaming: boolean) => void;
  readonly streamingTextRef: MutableRefObject<string>;
  readonly sessionIdRef: MutableRefObject<string | undefined>;
  readonly serverStopFailedLabel: string;
}

/** Provides stable UI actions for the writing session panel. */
export function useSessionPanelActions({
  input,
  proseBuffer,
  sendMessage,
  closeSocket,
  onClose,
  setInput,
  setMessages,
  setAddedIds,
  setProseBuffer,
  setStreamingText,
  setIsStreaming,
  streamingTextRef,
  sessionIdRef,
  serverStopFailedLabel,
}: UseSessionPanelActionsOptions) {
  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text) return;
    setMessages((prev) => [...prev, { id: `user-${Date.now()}`, role: "user", content: text }]);
    sendMessage("user_direction", text);
    setInput("");
  }, [input, sendMessage, setInput, setMessages]);

  const handleAddToDraft = useCallback(
    (msgId: string, prose: string) => {
      setAddedIds((prev) => new Set(prev).add(msgId));
      setProseBuffer((prev) => (prev ? `${prev}\n\n${prose}` : prose));
    },
    [setAddedIds, setProseBuffer],
  );

  const handleSaveToChapter = useCallback(() => {
    if (!proseBuffer) return;
    sendMessage("save_to_chapter", proseBuffer);
  }, [proseBuffer, sendMessage]);

  const handleGenerateDraft = useCallback(() => {
    sendMessage("generate_draft");
  }, [sendMessage]);

  /** Stop Generation — aborts only current AI stream, session stays active. */
  const handleStopGeneration = useCallback(() => {
    const sent = sendMessage("stop_generation");
    if (!sent) {
      setMessages((prev) => [
        ...prev,
        {
          id: `stop-failed-${Date.now()}`,
          role: "system",
          content: serverStopFailedLabel,
        },
      ]);
    }
    streamingTextRef.current = "";
    setStreamingText("");
    setIsStreaming(false);
  }, [
    sendMessage,
    serverStopFailedLabel,
    setIsStreaming,
    setMessages,
    setStreamingText,
    streamingTextRef,
  ]);

  const handleEndSession = useCallback(() => {
    closeSocket();
    onClose();
  }, [closeSocket, onClose]);

  const handleRecoverSession = useCallback(() => {
    const sessionId = sessionIdRef.current;
    if (!sessionId) return;
    sendMessage("recover_session", undefined, { session_id: sessionId });
  }, [sendMessage, sessionIdRef]);

  return {
    handleAddToDraft,
    handleEndSession,
    handleGenerateDraft,
    handleRecoverSession,
    handleSaveToChapter,
    handleSend,
    handleStopGeneration,
  };
}
