"use client";

/**
 * SentimentPanelHeader — panel header with title, refresh, and close controls.
 *
 * Includes the deterministic-analysis disclaimer bar.
 */

import { ArrowLeft, Info, RefreshCw, TrendingUp, X } from "lucide-react";

interface SentimentPanelHeaderProps {
  onClose: () => void;
  showRefresh: boolean;
  isPending: boolean;
  onRefresh: () => void;
  title: string;
  disclaimer: string;
  closeLabel: string;
  refreshLabel: string;
}

export function SentimentPanelHeader({
  onClose,
  showRefresh,
  isPending,
  onRefresh,
  title,
  disclaimer,
  closeLabel,
  refreshLabel,
}: SentimentPanelHeaderProps) {
  return (
    <>
      {/* Header bar */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
            aria-label={closeLabel}
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <TrendingUp className="w-5 h-5 text-blue-500 flex-shrink-0" />
            <h3 className="font-medium truncate">{title}</h3>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {showRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors disabled:opacity-50"
              aria-label={refreshLabel}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isPending ? "animate-spin" : ""}`} />
              {refreshLabel}
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
            aria-label={closeLabel}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Deterministic disclaimer */}
      <div className="px-4 py-1.5 border-b border-border bg-muted/30">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5 flex-shrink-0" />
          {disclaimer}
        </p>
      </div>
    </>
  );
}
