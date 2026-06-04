"use client";

import { Check, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { ExtractedEvent } from "@/types/timeline";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ExtractedEventCardProps {
  readonly event: ExtractedEvent;
  readonly decision: "accepted" | "rejected" | undefined;
  readonly isConfirmPending: boolean;
  readonly onAccept: (event: ExtractedEvent) => void;
  readonly onReject: (eventId: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Review card for a single extracted timeline event. */
export function ExtractedEventCard({
  event,
  decision,
  isConfirmPending,
  onAccept,
  onReject,
}: ExtractedEventCardProps) {
  const t = useTranslations("timeline");
  const isDecided = decision !== undefined;

  return (
    <div className={cn("p-3 rounded-lg border border-border bg-card", isDecided && "opacity-60")}>
      <div className="flex items-start gap-2">
        <span className="text-base leading-none" aria-hidden="true">
          {"\uD83D\uDCDD"}
        </span>
        <span className="text-sm font-medium text-[var(--color-text-primary)]">
          {"\u201C"}
          {event.expression}
          {"\u201D"}
        </span>
      </div>

      <p className="text-xs text-muted-foreground mt-1">
        {t("eventName")}: {event.event_name}
      </p>
      <p className="text-xs text-muted-foreground">
        {t("chapter")}: {event.chapter_reference}
      </p>

      {event.character_names.length > 0 && (
        <div className="flex items-center gap-1 mt-1.5 flex-wrap">
          {event.character_names.map((name) => (
            <span
              key={name}
              className="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded-full bg-[var(--color-bg-secondary)] text-muted-foreground"
            >
              {name}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 mt-1.5">
        <span className="text-[10px] text-muted-foreground">{t("confidence")}</span>
        <div className="flex-1 h-1.5 bg-[var(--color-bg-secondary)] rounded-full overflow-hidden max-w-24">
          <div
            className="h-full bg-[var(--color-accent)] rounded-full"
            style={{ width: `${Math.round(event.confidence * 100)}%` }}
          />
        </div>
        <span className="text-[10px] text-muted-foreground">
          {Math.round(event.confidence * 100)}%
        </span>
      </div>

      <p className="text-xs text-muted-foreground mt-1.5 italic leading-relaxed">
        {t("context")}: {"\u201C"}
        {event.context}
        {"\u201D"}
      </p>

      <div className="flex items-center gap-2 mt-2">
        {decision === undefined ? (
          <>
            <button
              type="button"
              onClick={() => onAccept(event)}
              disabled={isConfirmPending}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md border border-green-300 text-green-700 hover:bg-green-50 transition-colors disabled:opacity-50 dark:border-green-700 dark:text-green-400 dark:hover:bg-green-950"
            >
              <Check className="w-3 h-3" />
              {t("accept")}
            </button>
            <button
              type="button"
              onClick={() => onReject(event.id)}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md border border-red-300 text-red-700 hover:bg-red-50 transition-colors dark:border-red-700 dark:text-red-400 dark:hover:bg-red-950"
            >
              <X className="w-3 h-3" />
              {t("reject")}
            </button>
          </>
        ) : (
          <span
            className={cn(
              "text-xs font-medium",
              decision === "accepted"
                ? "text-green-600 dark:text-green-400"
                : "text-red-600 dark:text-red-400",
            )}
          >
            {decision === "accepted" ? t("accepted") : t("rejected")}
          </span>
        )}
      </div>
    </div>
  );
}
