"use client";

import { ArrowLeft, RefreshCw, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BetaReaderHeaderProps {
  readonly viewState: "idle" | "loading" | "results" | "error";
  readonly isPending: boolean;
  readonly onClose: () => void;
  readonly onRefresh: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Header controls for the beta reader side panel. */
export function BetaReaderHeader({
  viewState,
  isPending,
  onClose,
  onRefresh,
}: BetaReaderHeaderProps) {
  const t = useTranslations("analysis");

  return (
    <div className="flex items-center justify-between p-4 border-b border-border bg-card">
      <div className="flex items-center gap-3 min-w-0">
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
          aria-label={t("close")}
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <Sparkles className="w-5 h-5 text-purple-500 flex-shrink-0" />
        <h3 className="font-medium truncate">{t("title")}</h3>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {viewState === "results" && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isPending ? "animate-spin" : ""}`} />
            {t("refresh")}
          </button>
        )}
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
          aria-label={t("close")}
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
