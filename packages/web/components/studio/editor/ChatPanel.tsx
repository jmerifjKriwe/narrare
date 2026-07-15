"use client";

/**
 * ChatPanel — ChatGPT-style free-form chat sidebar (right panel).
 *
 * Uses SSE streaming (POST /api/v1/chat) for Q&A-style writing craft
 * conversations. Simpler than SessionPanel: no prose/draft features,
 * no "add to chapter" — just send message, receive response.
 *
 * Reuses the existing ChatMessage component for rendering.
 * Auto-manages conversation_id (creates on first message, reuses).
 * Supports AbortController for cancel-in-flight.
 */

import { Bot, Loader2, MessageSquare, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { StatusMessage } from "@/components/ui/status-message";
import { useChat } from "@/lib/hooks/useChat";
import { ChatInputArea } from "./ChatInputArea";
import { ChatMessage } from "./ChatMessage";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatPanelProps {
  readonly projectId: string;
  readonly onClose: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChatPanel({ projectId, onClose }: ChatPanelProps) {
  const t = useTranslations("studio");
  const {
    messages,
    isStreaming,
    error,
    retry,
    sendMessage,
    clearConversation,
    cancelStream,
    chatEndRef,
  } = useChat(projectId);

  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const aiDraftBadge = t("sessionPanel.aiDraftBadge");
  const addToDraftLabel = t("aiActions.addToDraft");
  const addedToDraftLabel = t("sessionPanel.addedToDraft");

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || isStreaming) return;
    void sendMessage(text);
    setInput("");
  }, [input, isStreaming, sendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (isStreaming) {
        cancelStream();
      } else {
        onClose();
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [isStreaming, cancelStream, onClose]);

  return (
    <div className="flex flex-col h-full border-l border-border bg-card w-80">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <MessageSquare className="w-4 h-4 text-primary" />
          <span>{t("chatPanel.title")}</span>
          <span
            className={`w-2 h-2 rounded-full ${isStreaming ? "bg-green-500" : "bg-muted-foreground/40"}`}
            title={isStreaming ? t("chatPanel.connected") : t("chatPanel.disconnected")}
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

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
        {messages.length === 0 && !isStreaming && (
          <div className="flex flex-col items-center justify-center flex-1 text-center text-muted-foreground gap-2">
            <MessageSquare className="w-8 h-8 opacity-40" />
            <p className="text-sm">{t("chatPanel.newConversation")}</p>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            message={msg}
            isAdded={false}
            onAddToDraft={() => {}}
            aiDraftBadge={aiDraftBadge}
            addToDraftLabel={addToDraftLabel}
            addedToDraftLabel={addedToDraftLabel}
            projectId={projectId}
          />
        ))}

        {isStreaming && (
          <div className="flex justify-start">
            <div className="flex items-start gap-2">
              <Bot className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
              <div className="px-3 py-2 rounded-lg bg-muted text-sm text-foreground">
                <Loader2 className="inline w-4 h-4 animate-spin text-muted-foreground" />
                <span className="ml-2 text-xs text-muted-foreground">
                  {t("chatPanel.streaming")}
                </span>
              </div>
            </div>
          </div>
        )}

        {error && (
          <StatusMessage
            state="error"
            message={error.userMessage}
            action={
              error.retryable ? (
                <button
                  type="button"
                  onClick={() => retry()}
                  className="text-xs font-medium text-primary hover:underline"
                >
                  {t("aiActions.retry")}
                </button>
              ) : undefined
            }
          />
        )}

        <div ref={chatEndRef} />
      </div>

      <ChatInputArea
        inputRef={inputRef}
        input={input}
        onInputChange={setInput}
        onKeyDown={handleKeyDown}
        isStreaming={isStreaming}
        onSend={handleSend}
        onCancelStream={cancelStream}
        onClearConversation={clearConversation}
        hasMessages={messages.length > 0}
        t={t}
      />
    </div>
  );
}
