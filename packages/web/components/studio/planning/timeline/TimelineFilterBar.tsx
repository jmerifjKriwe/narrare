"use client";

import { Plus, X } from "lucide-react";
import { useTranslations } from "next-intl";
import type { TimelineEventSource, TimelineEventType, TimelineFilters } from "@/types/timeline";

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

const EVENT_SOURCES: TimelineEventSource[] = ["manual", "ai_analysis", "extracted"];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TimelineFilterBarProps {
  readonly filters: TimelineFilters;
  readonly setFilters: React.Dispatch<React.SetStateAction<TimelineFilters>>;
  readonly onAddEvent: () => void;
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

function sourceLabel(source: TimelineEventSource): string {
  const map: Record<TimelineEventSource, string> = {
    manual: "manual",
    ai_analysis: "aiAnalysis",
    extracted: "extracted",
  };
  return map[source] ?? source;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Filter controls and create button for the timeline event list. */
export function TimelineFilterBar({ filters, setFilters, onAddEvent }: TimelineFilterBarProps) {
  const t = useTranslations("timeline");

  return (
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
            setFilters((prev) => ({ ...prev, is_confirmed: e.target.checked || undefined }))
          }
          className="rounded border-border"
        />
        {t("showConfirmedOnly")}
      </label>

      <button
        type="button"
        onClick={() => setFilters({})}
        className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        aria-label="Clear filters"
      >
        <X className="w-3 h-3" />
      </button>

      <div className="flex-1" />

      <button
        type="button"
        onClick={onAddEvent}
        className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity"
      >
        <Plus className="w-3.5 h-3.5" />
        {t("addEvent")}
      </button>
    </div>
  );
}
