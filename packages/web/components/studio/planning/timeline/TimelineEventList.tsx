"use client";

import { Loader2, Plus, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useTimelineEvents } from "@/lib/hooks/useTimeline";
import type { TimelineEventSource, TimelineEventType, TimelineFilters } from "@/types/timeline";
import { TimelineEventCard } from "./TimelineEventCard";
import { TimelineEventForm } from "./TimelineEventForm";

interface TimelineEventListProps {
  novelId: string;
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

const EVENT_SOURCES: TimelineEventSource[] = ["manual", "ai_analysis", "extracted"];

/** Map event type enum values to i18n keys. */
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

/** Map source enum values to i18n keys. */
function sourceLabel(source: TimelineEventSource): string {
  const map: Record<TimelineEventSource, string> = {
    manual: "manual",
    ai_analysis: "aiAnalysis",
    extracted: "extracted",
  };
  return map[source] ?? source;
}

/** Displays a filterable list of timeline events with add/edit capabilities. */
export function TimelineEventList({ novelId }: TimelineEventListProps) {
  const t = useTranslations("timeline");

  const [filters, setFilters] = useState<TimelineFilters>({});
  const [showForm, setShowForm] = useState(false);
  const [editingEventId, setEditingEventId] = useState<string | null>(null);

  const { data: events, isLoading, error } = useTimelineEvents(novelId, filters);

  if (error) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-[var(--color-error)]">
        {t("errorLoading")}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">{t("loading")}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <select
          value={filters.event_type ?? ""}
          onChange={(e) =>
            setFilters((prev) => ({
              ...prev,
              event_type: (e.target.value || undefined) as TimelineEventType | undefined,
            }))
          }
          className="text-xs border border-border rounded px-2 py-1 bg-card"
          aria-label={t("filterByType")}
        >
          <option value="">{t("filterByType")}</option>
          {EVENT_TYPES.map((type) => (
            <option key={type} value={type}>
              {t(eventTypeLabel(type))}
            </option>
          ))}
        </select>

        <select
          value={filters.source ?? ""}
          onChange={(e) =>
            setFilters((prev) => ({
              ...prev,
              source: (e.target.value || undefined) as TimelineEventSource | undefined,
            }))
          }
          className="text-xs border border-border rounded px-2 py-1 bg-card"
          aria-label={t("filterBySource")}
        >
          <option value="">{t("filterBySource")}</option>
          {EVENT_SOURCES.map((src) => (
            <option key={src} value={src}>
              {t(sourceLabel(src))}
            </option>
          ))}
        </select>

        <label className="flex items-center gap-1 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={filters.is_confirmed ?? false}
            onChange={(e) =>
              setFilters((prev) => ({
                ...prev,
                is_confirmed: e.target.checked || undefined,
              }))
            }
            className="rounded border-border"
          />
          {t("showConfirmedOnly")}
        </label>

        <button
          type="button"
          onClick={() => {
            setFilters({});
          }}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Clear filters"
        >
          <X className="w-3 h-3" />
        </button>

        <div className="flex-1" />

        <button
          type="button"
          onClick={() => {
            setEditingEventId(null);
            setShowForm(true);
          }}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity"
        >
          <Plus className="w-3.5 h-3.5" />
          {t("addEvent")}
        </button>
      </div>

      {/* Event list */}
      {!events || events.length === 0 ? (
        <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
          {t("noEvents")}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {events.map((event) => (
            <TimelineEventCard
              key={event.id}
              event={event}
              novelId={novelId}
              onEdit={() => {
                setEditingEventId(event.id);
                setShowForm(true);
              }}
            />
          ))}
        </div>
      )}

      {/* Create/Edit form modal */}
      {showForm && (
        <TimelineEventForm
          novelId={novelId}
          eventId={editingEventId}
          onClose={() => {
            setShowForm(false);
            setEditingEventId(null);
          }}
        />
      )}
    </div>
  );
}
