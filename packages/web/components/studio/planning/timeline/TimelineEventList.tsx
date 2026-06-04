"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useTimelineEvents } from "@/lib/hooks/useTimeline";
import type { TimelineFilters } from "@/types/timeline";
import { TimelineEventCard } from "./TimelineEventCard";
import { TimelineEventForm } from "./TimelineEventForm";
import { TimelineFilterBar } from "./TimelineFilterBar";

interface TimelineEventListProps {
  novelId: string;
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
      <TimelineFilterBar
        filters={filters}
        setFilters={setFilters}
        onAddEvent={() => {
          setEditingEventId(null);
          setShowForm(true);
        }}
      />

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
