"use client";

/**
 * TimelineVisualization — Interactive timeline view (PLAN-004 Phase 3).
 *
 * Three sub-views: Chronological, By Chapter, By Character.
 * CSS-based layout (no new dependencies). Shows cause → consequence
 * connections and character age data.
 */

import { useTranslations } from "next-intl";
import { useState } from "react";
import { useCharacterAges, useTimelineEvents } from "@/lib/hooks/useTimeline";
import { cn } from "@/lib/utils";
import { ByChapterView } from "./ByChapterView";
import { ByCharacterView } from "./ByCharacterView";
import { ChronologicalView } from "./ChronologicalView";

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
