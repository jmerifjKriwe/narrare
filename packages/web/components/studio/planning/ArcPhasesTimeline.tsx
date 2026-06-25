"use client";

/**
 * ArcPhasesTimeline — visual timeline of character arc phases.
 *
 * Extracted from CharacterArcResult for modularity (RULE-04). Renders each
 * phase as a numbered step with its description, emotional state, turning
 * point, and suggested chapters.
 *
 * @module ArcPhasesTimeline
 */

import { useTranslations } from "next-intl";
import type { ArcPhaseResponse } from "@/lib/api/character-arc";

interface ArcPhasesTimelineProps {
  readonly phases: ArcPhaseResponse[];
}

/** Renders a character arc's phases as a vertical numbered timeline. */
export function ArcPhasesTimeline({ phases }: ArcPhasesTimelineProps) {
  const t = useTranslations("studio");

  if (phases.length === 0) return null;

  return (
    <ol className="flex flex-col gap-3" aria-label={t("characterArc.phases")}>
      {phases.map((phase, index) => {
        const stableKey = `${phase.phase_name}-${phase.emotional_state}-${index}`;
        return (
          <li key={stableKey} className="flex gap-3 rounded-lg border border-border bg-card p-3">
            {/* Step number badge */}
            <span
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent)] text-xs font-semibold text-white"
              aria-hidden="true"
            >
              {index + 1}
            </span>

            <div className="flex min-w-0 flex-col gap-1">
              {phase.phase_name && (
                <h4 className="text-sm font-semibold text-[var(--color-text-primary)]">
                  {phase.phase_name}
                </h4>
              )}
              {phase.description && (
                <p className="text-xs text-muted-foreground leading-relaxed">{phase.description}</p>
              )}

              <dl className="mt-1 flex flex-col gap-1">
                {phase.emotional_state && (
                  <div className="flex flex-wrap gap-1">
                    <dt className="text-[0.6875rem] font-medium uppercase tracking-wide text-muted-foreground">
                      {t("characterArc.emotionalState")}:
                    </dt>
                    <dd className="text-[0.6875rem] text-[var(--color-text-secondary)]">
                      {phase.emotional_state}
                    </dd>
                  </div>
                )}
                {phase.turning_point && (
                  <div className="flex flex-wrap gap-1">
                    <dt className="text-[0.6875rem] font-medium uppercase tracking-wide text-muted-foreground">
                      {t("characterArc.turningPoint")}:
                    </dt>
                    <dd className="text-[0.6875rem] text-[var(--color-text-secondary)]">
                      {phase.turning_point}
                    </dd>
                  </div>
                )}
                {phase.chapters_suggested && (
                  <div className="flex flex-wrap gap-1">
                    <dt className="text-[0.6875rem] font-medium uppercase tracking-wide text-muted-foreground">
                      {t("characterArc.chaptersSuggested")}:
                    </dt>
                    <dd className="text-[0.6875rem] text-[var(--color-text-secondary)]">
                      {phase.chapters_suggested}
                    </dd>
                  </div>
                )}
              </dl>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
