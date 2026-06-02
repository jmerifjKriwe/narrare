"use client";

/**
 * TimelineVisualization — Interactive timeline view (PLAN-004 Phase 3).
 *
 * Three sub-views: Chronological, By Chapter, By Character.
 * CSS-based layout (no new dependencies). Shows cause → consequence
 * connections and character age data.
 */

import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { useCharacterAges, useTimelineEvents } from "@/lib/hooks/useTimeline";
import { cn } from "@/lib/utils";
import type { TimelineEvent } from "@/types/timeline";

type ViewMode = "chronological" | "chapter" | "character";

interface TimelineVisualizationProps {
  novelId: string;
}

// --- View mode tabs ---

function ViewModeTabs({ mode, onChange }: { mode: ViewMode; onChange: (m: ViewMode) => void }) {
  const t = useTranslations("timeline");
  const tabs: { key: ViewMode; label: string }[] = [
    { key: "chronological", label: t("chronologicalView") },
    { key: "chapter", label: t("byChapterView") },
    { key: "character", label: t("byCharacterView") },
  ];

  return (
    <div className="flex gap-1 mb-3">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onChange(tab.key)}
          className={cn(
            "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
            mode === tab.key
              ? "bg-[var(--color-accent)] text-white"
              : "bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] hover:bg-[var(--color-accent-light)]",
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

// --- Character age panel ---

function CharacterAgePanel({ novelId }: { novelId: string }) {
  const t = useTranslations("timeline");
  const { data: ageReport } = useCharacterAges(novelId);

  if (!ageReport || ageReport.characters.length === 0) return null;

  return (
    <div className="mb-4 p-3 rounded-md bg-[var(--color-bg-secondary)] border border-border">
      <h4 className="text-xs font-semibold mb-2 text-[var(--color-text-primary)]">
        {t("characterAges")}
      </h4>
      <div className="flex flex-wrap gap-2">
        {ageReport.characters.map((char) => (
          <span
            key={char.character_id ?? char.character_name}
            className={cn(
              "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs",
              char.age_available
                ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
                : "bg-[var(--color-bg-primary)] text-[var(--color-text-tertiary)]",
            )}
          >
            {char.character_name}
            {char.age_available && char.birth_date_narrative
              ? ` (${char.birth_date_narrative})`
              : char.age_available && char.birth_date
                ? ` (${char.birth_date})`
                : ` — ${t("ageUnknown")}`}
          </span>
        ))}
      </div>
      <p className="mt-2 text-xs text-[var(--color-text-tertiary)]">
        {t("charactersWithAge", { count: ageReport.characters_with_age })} ·{" "}
        {t("charactersWithoutAge", { count: ageReport.characters_without_age })}
      </p>
    </div>
  );
}

// --- Chronological view ---

function ChronologicalView({ events }: { events: TimelineEvent[] }) {
  const t = useTranslations("timeline");
  const sorted = useMemo(
    () =>
      [...events].sort((a, b) => {
        const orderA = a.temporal_order ?? 0;
        const orderB = b.temporal_order ?? 0;
        return orderA - orderB;
      }),
    [events],
  );

  if (sorted.length === 0) {
    return <p className="text-sm text-[var(--color-text-tertiary)]">{t("noEventsToVisualize")}</p>;
  }

  return (
    <div className="relative pl-6 border-l-2 border-[var(--color-accent)]/30 space-y-4">
      {sorted.map((event) => (
        <div key={event.id} className="relative">
          {/* Timeline dot */}
          <div className="absolute -left-[calc(1.5rem+5px)] top-1.5 w-2.5 h-2.5 rounded-full bg-[var(--color-accent)]" />

          {/* Timestamp */}
          {event.timestamp_raw && (
            <p className="text-xs font-semibold text-[var(--color-accent)] mb-0.5">
              {event.timestamp_raw}
            </p>
          )}

          {/* Event card */}
          <div className="rounded-md bg-[var(--color-bg-card)] border border-border p-3">
            <p className="text-sm font-medium text-[var(--color-text-primary)]">
              {event.event_name}
            </p>

            {/* Characters */}
            {event.character_refs.length > 0 && (
              <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                {t("characters")}: {event.character_refs.map((c) => c.name).join(", ")}
              </p>
            )}

            {/* Chapter */}
            {event.chapter_id && (
              <p className="text-xs text-[var(--color-text-tertiary)]">
                {t("chapter")}: {event.chapter_id}
              </p>
            )}

            {/* Causal links */}
            {(event.causes || event.consequences) && (
              <div className="mt-2 flex flex-col gap-0.5">
                {event.causes && (
                  <p className="text-xs text-[var(--color-text-tertiary)]">
                    ← {t("causedBy")}: {event.causes}
                  </p>
                )}
                {event.consequences && (
                  <p className="text-xs text-[var(--color-text-tertiary)]">
                    → {t("leadsTo")}: {event.consequences}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// --- By Chapter view ---

function ByChapterView({ events }: { events: TimelineEvent[] }) {
  const t = useTranslations("timeline");

  const grouped = useMemo(() => {
    const map = new Map<string, TimelineEvent[]>();
    for (const event of events) {
      const key = event.chapter_id ?? "__no_chapter__";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(event);
    }
    // Sort events within each chapter by temporal_order
    for (const [, evts] of map) {
      evts.sort((a, b) => (a.temporal_order ?? 0) - (b.temporal_order ?? 0));
    }
    return map;
  }, [events]);

  if (events.length === 0) {
    return <p className="text-sm text-[var(--color-text-tertiary)]">{t("noEventsToVisualize")}</p>;
  }

  if (grouped.size === 1 && grouped.has("__no_chapter__")) {
    return <p className="text-sm text-[var(--color-text-tertiary)]">{t("noChapters")}</p>;
  }

  return (
    <div className="space-y-4">
      {[...grouped.entries()].map(([chapterId, evts]) => (
        <div key={chapterId}>
          <h4 className="text-xs font-semibold text-[var(--color-accent)] mb-2">
            {chapterId === "__no_chapter__" ? t("noChapter") : `${t("chapter")} ${chapterId}`}
          </h4>
          <div className="flex flex-wrap gap-2">
            {evts.map((event) => (
              <div
                key={event.id}
                className="px-3 py-1.5 rounded-md bg-[var(--color-bg-card)] border border-border text-sm"
              >
                {event.event_name}
              </div>
            ))}
          </div>
          {/* Connection arrows between sequential events */}
          {evts.length > 1 && (
            <div className="flex flex-wrap gap-1 mt-1 ml-2 text-xs text-[var(--color-text-tertiary)]">
              {evts.map((event, i) => (
                <span key={event.id}>
                  {i > 0 && <span className="mx-1">→</span>}
                  {event.event_name}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// --- By Character view ---

function ByCharacterView({ events }: { events: TimelineEvent[] }) {
  const t = useTranslations("timeline");

  const grouped = useMemo(() => {
    const map = new Map<string, TimelineEvent[]>();
    for (const event of events) {
      for (const ref of event.character_refs) {
        if (!map.has(ref.name)) map.set(ref.name, []);
        map.get(ref.name)!.push(event);
      }
    }
    // Sort events for each character by temporal_order
    for (const [, evts] of map) {
      evts.sort((a, b) => (a.temporal_order ?? 0) - (b.temporal_order ?? 0));
    }
    return map;
  }, [events]);

  if (events.length === 0) {
    return <p className="text-sm text-[var(--color-text-tertiary)]">{t("noEventsToVisualize")}</p>;
  }

  if (grouped.size === 0) {
    return <p className="text-sm text-[var(--color-text-tertiary)]">{t("noCharacterRefs")}</p>;
  }

  return (
    <div className="space-y-4">
      {[...grouped.entries()].map(([characterName, evts]) => (
        <div key={characterName}>
          <h4 className="text-xs font-semibold text-[var(--color-accent)] mb-2">{characterName}</h4>
          <div className="flex flex-wrap gap-2 ml-2">
            {evts.map((event) => (
              <div
                key={event.id}
                className="px-3 py-1.5 rounded-md bg-[var(--color-bg-card)] border border-border text-sm"
              >
                {event.timestamp_raw && (
                  <span className="text-[var(--color-text-tertiary)] mr-1">
                    {event.timestamp_raw}:
                  </span>
                )}
                {event.event_name}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// --- Main component ---

export function TimelineVisualization({ novelId }: TimelineVisualizationProps) {
  const t = useTranslations("timeline");
  const [viewMode, setViewMode] = useState<ViewMode>("chronological");
  const { data: events = [], isLoading } = useTimelineEvents(novelId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-[var(--color-text-tertiary)]">{t("loadingVisualization")}</p>
      </div>
    );
  }

  return (
    <div className="p-4">
      <ViewModeTabs mode={viewMode} onChange={setViewMode} />
      <CharacterAgePanel novelId={novelId} />

      {viewMode === "chronological" && <ChronologicalView events={events} />}
      {viewMode === "chapter" && <ByChapterView events={events} />}
      {viewMode === "character" && <ByCharacterView events={events} />}
    </div>
  );
}
