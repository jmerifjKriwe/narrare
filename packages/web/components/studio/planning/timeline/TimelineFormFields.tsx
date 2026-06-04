"use client";

import { useTranslations } from "next-intl";
import type { TimelineEventType } from "@/types/timeline";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TimelineFormFieldsProps {
  readonly eventName: string;
  readonly setEventName: (value: string) => void;
  readonly description: string;
  readonly setDescription: (value: string) => void;
  readonly eventType: TimelineEventType;
  readonly setEventType: (value: TimelineEventType) => void;
  readonly timestampRaw: string;
  readonly setTimestampRaw: (value: string) => void;
  readonly temporalOrder: string;
  readonly setTemporalOrder: (value: string) => void;
  readonly causes: string;
  readonly setCauses: (value: string) => void;
  readonly consequences: string;
  readonly setConsequences: (value: string) => void;
  readonly validationError: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function eventTypeLabel(type: TimelineEventType): string {
  const map: Record<TimelineEventType, string> = {
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
  return map[type] ?? type;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Field controls for timeline event creation and editing. */
export function TimelineFormFields({
  eventName,
  setEventName,
  description,
  setDescription,
  eventType,
  setEventType,
  timestampRaw,
  setTimestampRaw,
  temporalOrder,
  setTemporalOrder,
  causes,
  setCauses,
  consequences,
  setConsequences,
  validationError,
}: TimelineFormFieldsProps) {
  const t = useTranslations("timeline");

  return (
    <>
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

      <div>
        <label htmlFor="event-description" className="text-xs font-medium text-muted-foreground">
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
              {t(eventTypeLabel(type))}
            </option>
          ))}
        </select>
      </div>

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

      <div>
        <label htmlFor="event-consequences" className="text-xs font-medium text-muted-foreground">
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
    </>
  );
}
