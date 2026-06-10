"use client";

/**
 * StreamingBubble — AI streaming response indicator for SessionPanel.
 *
 * Extracted from SessionPanel for RULE-04 file size compliance.
 * Shows the streaming text with a spinning loader.
 */

import { Bot, Loader2 } from "lucide-react";

interface StreamingBubbleProps {
  readonly streamingText: string;
}

export function StreamingBubble({ streamingText }: StreamingBubbleProps) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] flex items-start gap-2">
        <Bot className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
        <div className="px-3 py-2 rounded-lg bg-muted text-sm text-foreground whitespace-pre-wrap">
          {streamingText}
          <Loader2 className="inline w-3 h-3 ml-1 animate-spin text-muted-foreground" />
        </div>
      </div>
    </div>
  );
}
