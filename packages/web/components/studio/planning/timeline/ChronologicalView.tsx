"use client";

import { useTranslations } from "next-intl";
import { useMemo } from "react";
import type { TimelineEvent } from "@/types/timeline";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChronologicalViewProps {
  readonly events: TimelineEvent[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Chronological timeline view sorted by temporal order. */
export function ChronologicalView({ events }: ChronologicalViewProps) {
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
          <div className="absolute -left-[calc(1.5rem+5px)] top-1.5 w-2.5 h-2.5 rounded-full bg-[var(--color-accent)]" />

          {event.timestamp_raw && (
            <p className="text-xs font-semibold text-[var(--color-accent)] mb-0.5">
              {event.timestamp_raw}
            </p>
          )}

          <div className="rounded-md bg-[var(--color-bg-card)] border border-border p-3">
            <p className="text-sm font-medium text-[var(--color-text-primary)]">
              {event.event_name}
            </p>

            {event.character_refs.length > 0 && (
              <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                {t("characters")}:{" "}
                {event.character_refs.map((character) => character.name).join(", ")}
              </p>
            )}

            {event.chapter_id && (
              <p className="text-xs text-[var(--color-text-tertiary)]">
                {t("chapter")}: {event.chapter_id}
              </p>
            )}

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
