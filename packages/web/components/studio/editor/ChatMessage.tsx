"use client";

import { Bot, Check, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { memo } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Message {
  readonly id: string;
  readonly role: "user" | "assistant" | "system";
  readonly content: string;
  readonly prose?: string;
}

interface ChatMessageProps {
  readonly message: Message;
  readonly isAdded: boolean;
  readonly onAddToDraft: (prose: string) => void;
  readonly aiDraftBadge: string;
  readonly addToDraftLabel: string;
  readonly addedToDraftLabel: string;
}

// ---------------------------------------------------------------------------
// Chat message bubble — memoized to avoid re-renders on scroll
// ---------------------------------------------------------------------------

export const ChatMessage = memo(function ChatMessage({
  message,
  isAdded,
  onAddToDraft,
  aiDraftBadge,
  addToDraftLabel,
  addedToDraftLabel,
}: ChatMessageProps): ReactNode {
  if (message.role === "system") {
    return (
      <div className="flex justify-center">
        <span className="px-3 py-1 rounded-full bg-muted text-xs text-muted-foreground">
          {message.content}
        </span>
      </div>
    );
  }

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm">
          {message.content}
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] flex flex-col gap-2">
        {/* Conversational text */}
        {message.content && (
          <div className="flex items-start gap-2">
            <Bot className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
            <p className="px-3 py-2 rounded-lg bg-muted text-sm text-foreground">
              {message.content}
            </p>
          </div>
        )}
        {/* Prose block */}
        {message.prose && (
          <div className="ml-7 border border-border rounded-lg overflow-hidden">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-primary/10 border-b border-border">
              <Sparkles className="w-3 h-3 text-primary" />
              <span className="text-xs font-medium text-primary">{aiDraftBadge}</span>
            </div>
            <div className="px-3 py-2 text-sm text-foreground whitespace-pre-wrap">
              {message.prose}
            </div>
            <div className="px-3 py-2 border-t border-border">
              <button
                type="button"
                onClick={() => onAddToDraft(message.prose!)}
                disabled={isAdded}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  isAdded
                    ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                    : "bg-primary text-primary-foreground hover:opacity-90"
                }`}
              >
                {isAdded ? (
                  <>
                    <Check className="w-3 h-3" />
                    <span>{addedToDraftLabel}</span>
                  </>
                ) : (
                  <span>{addToDraftLabel}</span>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});
