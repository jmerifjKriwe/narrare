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
import { TimelineFormFields } from "./TimelineFormFields";

interface TimelineEventFormProps {
  novelId: string;
  eventId: string | null;
  onClose: () => void;
}

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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-auto">
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

        <form onSubmit={handleSubmit} className="flex flex-col gap-3 p-4">
          <TimelineFormFields
            eventName={eventName}
            setEventName={setEventName}
            description={description}
            setDescription={setDescription}
            eventType={eventType}
            setEventType={setEventType}
            timestampRaw={timestampRaw}
            setTimestampRaw={setTimestampRaw}
            temporalOrder={temporalOrder}
            setTemporalOrder={setTemporalOrder}
            causes={causes}
            setCauses={setCauses}
            consequences={consequences}
            setConsequences={setConsequences}
            validationError={validationError}
          />

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
