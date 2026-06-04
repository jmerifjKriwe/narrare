"use client";

import { useTranslations } from "next-intl";
import { useMemo } from "react";
import type { TimelineEvent } from "@/types/timeline";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ByCharacterViewProps {
  readonly events: TimelineEvent[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Timeline events grouped by referenced character. */
export function ByCharacterView({ events }: ByCharacterViewProps) {
  const t = useTranslations("timeline");

  const grouped = useMemo(() => {
    const map = new Map<string, TimelineEvent[]>();
    for (const event of events) {
      for (const ref of event.character_refs) {
        if (!map.has(ref.name)) map.set(ref.name, []);
        map.get(ref.name)!.push(event);
      }
    }
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
