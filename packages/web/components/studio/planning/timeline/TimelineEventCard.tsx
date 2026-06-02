"use client";

import { Pencil, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useDeleteTimelineEvent } from "@/lib/hooks/useTimeline";
import { cn, truncate } from "@/lib/utils";
import type { TimelineEvent, TimelineEventSource, TimelineEventType } from "@/types/timeline";

interface TimelineEventCardProps {
  event: TimelineEvent;
  novelId: string;
  onEdit: () => void;
}

/** Source badge color mapping. */
const SOURCE_STYLES: Record<TimelineEventSource, string> = {
  manual: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  ai_analysis: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  extracted: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
};

/** Event type label key mapping. */
const EVENT_TYPE_LABELS: Record<TimelineEventType, string> = {
  plot_point: "plotPoint",
  character_event: "characterEvent",
  world_event: "worldEvent",
  flashback: "flashback",
  flashforward: "flashforward",
  birth: "birth",
  death: "death",
  battle: "battle",
  journey: "journey",
  other: "other",
};

/** Displays a single timeline event with actions. */
export function TimelineEventCard({ event, novelId, onEdit }: TimelineEventCardProps) {
  const t = useTranslations("timeline");
  const deleteMutation = useDeleteTimelineEvent(novelId);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const pendingAction = useRef<(() => void) | null>(null);

  const handleDelete = () => {
    pendingAction.current = () => deleteMutation.mutate(event.id);
    setConfirmOpen(true);
  };

  const sourceLabel = event.source === "ai_analysis" ? "aiAnalysis" : event.source;
  const typeLabel = EVENT_TYPE_LABELS[event.event_type] ?? event.event_type;

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border border-border bg-card hover:bg-[var(--color-bg-secondary)] transition-colors">
      {/* Main content */}
      <div className="flex-1 min-w-0">
        {/* Header row: name + badges */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-[var(--color-text-primary)] truncate">
            {event.event_name}
          </span>

          {/* Event type badge */}
          <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-[var(--color-bg-secondary)] text-muted-foreground">
            {t(typeLabel)}
          </span>

          {/* Source badge */}
          <span
            className={cn(
              "inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded-full",
              SOURCE_STYLES[event.source],
            )}
          >
            {t(sourceLabel)}
          </span>

          {/* Confirmed indicator for extracted events */}
          {event.source === "extracted" && (
            <span
              className={cn(
                "inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded-full",
                event.is_confirmed
                  ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                  : "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
              )}
            >
              {event.is_confirmed ? t("confirmed") : t("unconfirmed")}
            </span>
          )}
        </div>

        {/* Description (truncated) */}
        {event.description && (
          <p className="text-xs text-muted-foreground mt-1">{truncate(event.description, 120)}</p>
        )}

        {/* Metadata row */}
        <div className="flex items-center gap-3 mt-1.5 text-[11px] text-muted-foreground">
          {event.timestamp_raw && <span>{event.timestamp_raw}</span>}
          {event.temporal_order !== null && (
            <span>
              {t("temporalOrder")}: {event.temporal_order}
            </span>
          )}
        </div>

        {/* Character pills */}
        {event.character_refs.length > 0 && (
          <div className="flex items-center gap-1 mt-1.5 flex-wrap">
            {event.character_refs.map((char) => (
              <span
                key={char.id}
                className="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded-full bg-[var(--color-bg-secondary)] text-muted-foreground"
              >
                {char.name}
              </span>
            ))}
          </div>
        )}

        {/* Location */}
        {event.location_ref && (
          <div className="text-[11px] text-muted-foreground mt-1">📍 {event.location_ref.name}</div>
        )}

        {/* Confidence bar for AI events */}
        {event.confidence !== null && (
          <div className="flex items-center gap-2 mt-1.5">
            <span className="text-[10px] text-muted-foreground">{t("confidence")}</span>
            <div className="flex-1 h-1.5 bg-[var(--color-bg-secondary)] rounded-full overflow-hidden max-w-24">
              <div
                className="h-full bg-[var(--color-accent)] rounded-full"
                style={{ width: `${(event.confidence ?? 0) * 100}%` }}
              />
            </div>
            <span className="text-[10px] text-muted-foreground">
              {Math.round((event.confidence ?? 0) * 100)}%
            </span>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-1">
        <button
          type="button"
          onClick={onEdit}
          className="p-1 rounded hover:bg-[var(--color-bg-secondary)] transition-colors text-muted-foreground"
          aria-label={t("editEvent")}
        >
          <Pencil className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className="p-1 rounded hover:bg-[var(--color-bg-secondary)] transition-colors text-muted-foreground disabled:opacity-50"
          aria-label={t("deleteEvent")}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Delete confirmation */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("deleteEvent")}
        description={t("deleteConfirm")}
        confirmLabel={t("deleteEvent")}
        variant="destructive"
        onConfirm={() => {
          pendingAction.current?.();
          pendingAction.current = null;
          setConfirmOpen(false);
        }}
      />
    </div>
  );
}
