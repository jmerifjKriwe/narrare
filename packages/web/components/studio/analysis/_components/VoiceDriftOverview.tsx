"use client";

/**
 * VoiceDriftOverview — Layout γ heatmap overview (ANAL-009).
 *
 * Renders the always-visible characters × chapters heatmap: rows = characters,
 * columns = chapters (the union of every character's speaking chapters,
 * ordered by first appearance). Each cell is coloured by drift band (symbol +
 * match %) with a ⚡ jump marker on the `to` chapter of each jump. A
 * classification badge + overall match % cap each row.
 *
 * Clicking a row expands a {@link VoiceDriftDetailCard} inline (β-style drill-
 * in); other rows dim while one is expanded — the standard γ hybrid pattern.
 *
 * Chapters are labelled by their ordinal position across the whole-novel column
 * set (Ch1, Ch2…) since the backend carries only chapter ids. The per-row
 * rendering is extracted into {@link ./VoiceDriftOverviewRow} per RULE-04.
 *
 * @module VoiceDriftOverview
 */

import { useMemo, useState } from "react";
import type { VoiceDriftCharacterResult } from "@/lib/api/voice-drift-stream";
import { VoiceDriftDetailCard } from "./VoiceDriftDetailCard";
import { VoiceDriftOverviewRow } from "./VoiceDriftOverviewRow";

interface VoiceDriftOverviewProps {
  results: VoiceDriftCharacterResult[];
  /** scoped `analysis` translator. */
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function VoiceDriftOverview({ results, t }: VoiceDriftOverviewProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Union of all chapters across characters, ordered by first appearance.
  const { chapterIds, chapterLabel } = useMemo(() => {
    const seen = new Set<string>();
    const ids: string[] = [];
    for (const r of results) {
      for (const p of r.trend) {
        if (!seen.has(p.chapter_id)) {
          seen.add(p.chapter_id);
          ids.push(p.chapter_id);
        }
      }
    }
    const label = (chapterId: string): string => {
      const idx = ids.indexOf(chapterId);
      return idx >= 0 ? `Ch${idx + 1}` : chapterId;
    };
    return { chapterIds: ids, chapterLabel: label };
  }, [results]);

  const expanded = expandedId ? results.find((r) => r.character_id === expandedId) : null;

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto pb-1">
        <table className="w-full min-w-[680px] border-separate border-spacing-x-1.5">
          <thead>
            <tr>
              <th className="pb-1.5 text-left text-[11px] font-medium text-muted-foreground">
                {t("voiceDrift.character")}
              </th>
              {chapterIds.map((id) => (
                <th
                  key={id}
                  className="pb-1.5 text-center text-[11px] font-medium text-muted-foreground"
                >
                  {chapterLabel(id)}
                </th>
              ))}
              <th className="pb-1.5 pl-2 text-left text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                {t("voiceDrift.classificationHeader")}
              </th>
              <th className="pb-1.5 pl-2 text-left text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                {t("voiceDrift.overallHeader")}
              </th>
            </tr>
          </thead>
          <tbody>
            {results.map((result) => {
              const isExpanded = expandedId === result.character_id;
              const isDimmed = expandedId !== null && !isExpanded;
              const toggle = () => setExpandedId(isExpanded ? null : result.character_id);
              return (
                <VoiceDriftOverviewRow
                  key={result.character_id || result.character_name}
                  result={result}
                  chapterIds={chapterIds}
                  chapterLabel={chapterLabel}
                  isExpanded={isExpanded}
                  isDimmed={isDimmed}
                  onToggle={toggle}
                  t={t}
                />
              );
            })}
          </tbody>
        </table>
      </div>

      {expanded && <VoiceDriftDetailCard result={expanded} chapterLabel={chapterLabel} t={t} />}
    </div>
  );
}
