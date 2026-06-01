"use client";

import { Loader2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useCreateTimelineEvent, useUpdateTimelineEvent } from "@/lib/hooks/useTimeline";
import type {
  TimelineEventCreateRequest,
  TimelineEventType,
  TimelineEventUpdateRequest,
} from "@/types/timeline";

interface TimelineEventFormProps {
  novelId: string;
  eventId: string | null;
  onClose: () => void;
}

const EVENT_TYPES: TimelineEventType[] = [
  "plot_point",
  "character_event",
  "world_event",
  "flashback",
  "flashforward",
  "birth",
  "death",
  "battle",
  "journey",
  "other",
];

/** Modal/drawer form for creating or editing a timeline event. */
export function TimelineEventForm({ novelId, eventId, onClose }: TimelineEventFormProps) {
  const t = useTranslations("timeline");
  const isEditing = !!eventId;

  const createMutation = useCreateTimelineEvent(novelId);
  const updateMutation = useUpdateTimelineEvent(novelId);

  const [eventName, setEventName] = useState("");
  const [description, setDescription] = useState("");
  const [eventType, setEventType] = useState<TimelineEventType>("plot_point");
  const [timestampRaw, setTimestampRaw] = useState("");
  const [temporalOrder, setTemporalOrder] = useState<string>("");
  const [causes, setCauses] = useState("");
  const [consequences, setConsequences] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const isPending = createMutation.isPending || updateMutation.isPending;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!eventName.trim()) {
      setValidationError(t("eventNameRequired"));
      return;
    }

    setValidationError(null);

    const parsedOrder = temporalOrder.trim() ? Number(temporalOrder) : null;

    if (isEditing && eventId) {
      const data: TimelineEventUpdateRequest = {
        event_name: eventName.trim() || undefined,
        description: description.trim() || undefined,
        event_type: eventType,
        timestamp_raw: timestampRaw.trim() || undefined,
        temporal_order: parsedOrder,
        causes: causes.trim() || undefined,
        consequences: consequences.trim() || undefined,
      };
      updateMutation.mutate(
        { eventId, data },
        { onSuccess: onClose, onError: () => setValidationError(t("errorSaving")) },
      );
    } else {
      const data: TimelineEventCreateRequest = {
        event_name: eventName.trim(),
        description: description.trim() || undefined,
        event_type: eventType,
        timestamp_raw: timestampRaw.trim() || undefined,
        temporal_order: parsedOrder,
        causes: causes.trim() || undefined,
        consequences: consequences.trim() || undefined,
      };
      createMutation.mutate(data, {
        onSuccess: onClose,
        onError: () => setValidationError(t("errorSaving")),
      });
    }
  };

  const typeLabel = (type: TimelineEventType): string => {
    const map: Record<string, string> = {
      plot_point: "plotPoint",
      character_event: "characterEvent",
      world_event: "worldEvent",
    };
    return t(map[type] ?? type);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-medium">{isEditing ? t("editEvent") : t("addEvent")}</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-[var(--color-bg-secondary)] transition-colors text-muted-foreground"
            aria-label={t("close")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-3 p-4">
          {/* Event Name (required) */}
          <div>
            <label htmlFor="event-name" className="text-xs font-medium text-muted-foreground">
              {t("eventName")} *
            </label>
            <input
              id="event-name"
              type="text"
              value={eventName}
              onChange={(e) => setEventName(e.target.value)}
              className="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
              placeholder={t("eventName")}
            />
            {validationError && (
              <p className="text-xs text-[var(--color-error)] mt-1">{validationError}</p>
            )}
          </div>

          {/* Description */}
          <div>
            <label
              htmlFor="event-description"
              className="text-xs font-medium text-muted-foreground"
            >
              {t("description")}
            </label>
            <textarea
              id="event-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)] resize-y"
            />
          </div>

          {/* Event Type */}
          <div>
            <label htmlFor="event-type" className="text-xs font-medium text-muted-foreground">
              {t("eventType")}
            </label>
            <select
              id="event-type"
              value={eventType}
              onChange={(e) => setEventType(e.target.value as TimelineEventType)}
              className="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
            >
              {EVENT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {typeLabel(type)}
                </option>
              ))}
            </select>
          </div>

          {/* Timestamp */}
          <div>
            <label htmlFor="event-timestamp" className="text-xs font-medium text-muted-foreground">
              {t("timestamp")}
            </label>
            <input
              id="event-timestamp"
              type="text"
              value={timestampRaw}
              onChange={(e) => setTimestampRaw(e.target.value)}
              className="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
              placeholder="e.g. Year of the Dragon, Spring"
            />
          </div>

          {/* Temporal Order */}
          <div>
            <label htmlFor="event-order" className="text-xs font-medium text-muted-foreground">
              {t("temporalOrder")}
            </label>
            <input
              id="event-order"
              type="number"
              value={temporalOrder}
              onChange={(e) => setTemporalOrder(e.target.value)}
              className="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
              placeholder="1, 2, 3..."
            />
          </div>

          {/* Causes */}
          <div>
            <label htmlFor="event-causes" className="text-xs font-medium text-muted-foreground">
              {t("causes")}
            </label>
            <textarea
              id="event-causes"
              value={causes}
              onChange={(e) => setCauses(e.target.value)}
              rows={2}
              className="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)] resize-y"
            />
          </div>

          {/* Consequences */}
          <div>
            <label
              htmlFor="event-consequences"
              className="text-xs font-medium text-muted-foreground"
            >
              {t("consequences")}
            </label>
            <textarea
              id="event-consequences"
              value={consequences}
              onChange={(e) => setConsequences(e.target.value)}
              rows={2}
              className="w-full mt-1 px-3 py-1.5 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)] resize-y"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-[var(--color-bg-secondary)] transition-colors"
            >
              {t("cancel")}
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="px-3 py-1.5 text-sm rounded-md bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {isPending ? (
                <span className="flex items-center gap-1">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  {t("saving")}
                </span>
              ) : isEditing ? (
                t("save")
              ) : (
                t("create")
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
