"use client";

import { useTranslations } from "next-intl";
import { useMemo } from "react";
import type { TimelineEvent } from "@/types/timeline";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ByChapterViewProps {
  readonly events: TimelineEvent[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Timeline events grouped by chapter. */
export function ByChapterView({ events }: ByChapterViewProps) {
  const t = useTranslations("timeline");

  const grouped = useMemo(() => {
    const map = new Map<string, TimelineEvent[]>();
    for (const event of events) {
      const key = event.chapter_id ?? "__no_chapter__";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(event);
    }
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
          {evts.length > 1 && (
            <div className="flex flex-wrap gap-1 mt-1 ml-2 text-xs text-[var(--color-text-tertiary)]">
              {evts.map((event, index) => (
                <span key={event.id}>
                  {index > 0 && <span className="mx-1">→</span>}
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
