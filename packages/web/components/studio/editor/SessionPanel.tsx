"use client";

import { Bot, Loader2, Send, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { type SessionResponse, WritingSessionSocket } from "@/lib/api/generation";
import { useAuthStore } from "@/lib/stores/authStore";
import type { Message } from "./ChatMessage";
import { ChatMessage } from "./ChatMessage";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SessionPanelProps {
  readonly chapterId: string;
  readonly novelId: string;
  readonly mode: "interactive_session" | "interview_assisted";
  readonly onClose: () => void;
}

// ---------------------------------------------------------------------------
// Interview greetings are loaded from i18n (sessionPanel.interviewGreetings)
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let messageCounter = 0;

function createMessageId(): string {
  messageCounter += 1;
  return `msg-${messageCounter}`;
}

// ---------------------------------------------------------------------------
// SessionPanel component
// ---------------------------------------------------------------------------

export function SessionPanel({ chapterId, novelId, mode, onClose }: SessionPanelProps) {
  const t = useTranslations("studio");
  const currentUser = useAuthStore((s) => s.user);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [proseBuffer, setProseBuffer] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set());
  const [saveNotification, setSaveNotification] = useState<string | null>(null);

  const socketRef = useRef<WritingSessionSocket | null>(null);
  const streamingTextRef = useRef("");
  const chatEndRef = useRef<HTMLDivElement>(null);

  // -------------------------------------------------------------------------
  // Auto-scroll on new content
  // -------------------------------------------------------------------------

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // -------------------------------------------------------------------------
  // Interview greetings from i18n
  // -------------------------------------------------------------------------

  const greetings: string[] = t.raw("sessionPanel.interviewGreetings");
  const greetingIndex = useMemo(
    () => Math.floor(Math.random() * greetings.length),
    [greetings.length],
  );

  // -------------------------------------------------------------------------
  // Interview mode: show local greeting immediately on mount
  // -------------------------------------------------------------------------

  useEffect(() => {
    if (mode === "interview_assisted" && messages.length === 0 && greetings.length > 0) {
      setMessages([
        {
          id: createMessageId(),
          role: "assistant",
          content: greetings[greetingIndex],
        },
      ]);
    }
  }, [mode, greetings, greetingIndex, messages.length]);

  // -------------------------------------------------------------------------
  // WebSocket lifecycle
  // -------------------------------------------------------------------------

  useEffect(() => {
    if (!currentUser?.id) return;

    const socket = new WritingSessionSocket(
      chapterId,
      (msg: SessionResponse) => {
        switch (msg.type) {
          case "greeting":
            // For interview mode, greeting is already shown locally
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
            // Already handled by local greeting — just mark connected
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
            if (prose) {
              setMessages((prev) => [
                ...prev,
                { id: createMessageId(), role: "assistant", content: "", prose },
              ]);
            }
            break;
          }

          case "draft_done": {
            const prose = msg.text ?? "";
            if (prose) {
              setMessages((prev) => [
                ...prev,
                { id: createMessageId(), role: "assistant", content: "", prose },
              ]);
            }
            break;
          }

          case "feedback_acknowledged":
            setMessages((prev) => [
              ...prev,
              {
                id: createMessageId(),
                role: "assistant",
                content: msg.message ?? "",
              },
            ]);
            break;

          case "saved":
            setSaveNotification(t("sessionPanel.saved"));
            setTimeout(() => setSaveNotification(null), 3000);
            break;

          case "timeout":
            setMessages((prev) => [
              ...prev,
              {
                id: createMessageId(),
                role: "system",
                content: msg.message ?? t("sessionPanel.sessionEnded"),
              },
            ]);
            setIsConnected(false);
            break;

          case "error":
            setMessages((prev) => [
              ...prev,
              {
                id: createMessageId(),
                role: "system",
                content: msg.message ?? t("sessionPanel.errorConnecting"),
              },
            ]);
            break;
        }
      },
      () => {
        setIsConnected(false);
      },
      currentUser?.id,
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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- socket reconnects when user/novel/chapter/mode changes
  }, [chapterId, t, currentUser?.id, novelId, mode]);

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || !socketRef.current) return;

    setMessages((prev) => [...prev, { id: createMessageId(), role: "user", content: text }]);
    socketRef.current.send({ type: "user_direction", content: text });
    setInput("");
  }, [input]);

  const handleAddToDraft = useCallback((msgId: string, prose: string) => {
    setAddedIds((prev) => new Set(prev).add(msgId));
    setProseBuffer((prev) => (prev ? `${prev}\n\n${prose}` : prose));
  }, []);

  const handleSaveToChapter = useCallback(() => {
    if (!socketRef.current || !proseBuffer) return;
    socketRef.current.send({ type: "save_to_chapter", text: proseBuffer });
  }, [proseBuffer]);

  const handleGenerateDraft = useCallback(() => {
    socketRef.current?.send({ type: "generate_draft" });
  }, []);

  const handleEndSession = useCallback(() => {
    socketRef.current?.send({ type: "end_session" });
    socketRef.current?.close();
    socketRef.current = null;
    setIsConnected(false);
    onClose();
  }, [onClose]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  // -------------------------------------------------------------------------
  // Derived
  // -------------------------------------------------------------------------

  const hasAddedAny = useMemo(() => addedIds.size > 0, [addedIds]);

  // Stable i18n strings for memoized child
  const aiDraftBadge = t("sessionPanel.aiDraftBadge");
  const addToDraftLabel = t("sessionPanel.addToDraft");
  const addedToDraftLabel = t("sessionPanel.addedToDraft");

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full border-l border-border bg-card w-80">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Bot className="w-4 h-4 text-primary" />
          <span>
            {mode === "interview_assisted"
              ? t("sessionPanel.interviewTitle")
              : t("sessionPanel.title")}
          </span>
          <span
            className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500"}`}
            title={isConnected ? t("sessionPanel.connected") : t("sessionPanel.disconnected")}
          />
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 rounded-md hover:bg-accent transition-colors"
          aria-label={t("sessionPanel.close")}
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            message={msg}
            isAdded={addedIds.has(msg.id)}
            onAddToDraft={(prose) => handleAddToDraft(msg.id, prose)}
            aiDraftBadge={aiDraftBadge}
            addToDraftLabel={addToDraftLabel}
            addedToDraftLabel={addedToDraftLabel}
          />
        ))}

        {/* Streaming indicator */}
        {isStreaming && streamingText && (
          <div className="flex justify-start">
            <div className="max-w-[85%] flex items-start gap-2">
              <Bot className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
              <div className="px-3 py-2 rounded-lg bg-muted text-sm text-foreground whitespace-pre-wrap">
                {streamingText}
                <Loader2 className="inline w-3 h-3 ml-1 animate-spin text-muted-foreground" />
              </div>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Save notification */}
      {saveNotification && (
        <div className="mx-4 mb-2 px-3 py-2 rounded-lg bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs font-medium text-center">
          {saveNotification}
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("sessionPanel.inputPlaceholder")}
            disabled={!isConnected}
            className="flex-1 px-3 py-2 border border-border rounded-lg bg-background text-foreground text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/20 disabled:opacity-50"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={!input.trim() || !isConnected}
            className="p-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label={t("sessionPanel.send")}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Action buttons */}
      <div className="border-t border-border px-4 py-3 flex gap-2">
        {mode === "interview_assisted" && messages.length >= 3 && (
          <button
            type="button"
            onClick={handleGenerateDraft}
            disabled={!isConnected || isStreaming}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-colors disabled:opacity-50"
          >
            <Sparkles className="w-4 h-4" />
            <span>{t("sessionPanel.generateDraft")}</span>
          </button>
        )}
        <button
          type="button"
          onClick={handleSaveToChapter}
          disabled={!hasAddedAny || !isConnected}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-border rounded-lg text-sm text-foreground hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span>{t("sessionPanel.saveToChapter")}</span>
        </button>
        <button
          type="button"
          onClick={handleEndSession}
          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm text-destructive hover:bg-destructive/10 transition-colors"
        >
          <span>{t("sessionPanel.endSession")}</span>
        </button>
      </div>
    </div>
  );
}
