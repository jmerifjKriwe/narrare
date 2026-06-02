"use client";

/**
 * SessionHeader — Header bar for the writing session panel.
 *
 * Shows session title, connection status indicator, and close button.
 */

import { Bot, X } from "lucide-react";
import type { ReactNode } from "react";

interface SessionHeaderProps {
  readonly title: string;
  readonly isConnected: boolean;
  readonly connectedLabel: string;
  readonly disconnectedLabel: string;
  readonly closeLabel: string;
  readonly onClose: () => void;
  readonly actions?: ReactNode;
}

export function SessionHeader({
  title,
  isConnected,
  connectedLabel,
  disconnectedLabel,
  closeLabel,
  onClose,
  actions,
}: SessionHeaderProps) {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-border">
      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <Bot className="w-4 h-4 text-primary" />
        <span>{title}</span>
        <span
          className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500"}`}
          title={isConnected ? connectedLabel : disconnectedLabel}
        />
      </div>
      <div className="flex items-center gap-2">
        {actions}
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 rounded-md hover:bg-accent transition-colors"
          aria-label={closeLabel}
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
