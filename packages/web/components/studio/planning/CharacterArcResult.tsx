"use client";

/**
 * CharacterArcResult — renders a completed character arc analysis.
 *
 * Extracted from CharacterArcPanel for modularity (RULE-04). Displays the
 * arc type badge, starting → ending state, phase timeline, key relationships,
 * internal conflict, and resolution.
 *
 * @module CharacterArcResult
 */

import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ArcType, CharacterArcResponse } from "@/lib/api/character-arc";
import { cn } from "@/lib/utils";
import { ArcPhasesTimeline } from "./ArcPhasesTimeline";

interface CharacterArcResultProps {
  readonly result: CharacterArcResponse;
}

/** Badge color classes per known arc type. Unknown types use a neutral style. */
const ARC_BADGE_STYLES: Record<ArcType, string> = {
  growth: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  fall: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  transformation: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  flat: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200",
};

function isKnownArcType(value: string): value is ArcType {
  return value in ARC_BADGE_STYLES;
}

/** Badge class for an arc type; unknown types fall back to a neutral style. */
function getArcBadgeClass(arcType: string): string {
  return isKnownArcType(arcType)
    ? ARC_BADGE_STYLES[arcType]
    : "bg-[var(--color-bg-secondary)] text-muted-foreground";
}

/** Displays the full character arc analysis result. */
export function CharacterArcResult({ result }: CharacterArcResultProps) {
  const t = useTranslations("studio");

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4">
      {/* Header: character name + arc type badge */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h3 className="text-base font-semibold text-[var(--color-text-primary)]">
          {result.character_name}
        </h3>
        {result.arc_type && (
          <span
            className={cn(
              "inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full uppercase",
              getArcBadgeClass(result.arc_type),
            )}
          >
            {isKnownArcType(result.arc_type)
              ? t(`characterArc.arcType.${result.arc_type}`)
              : result.arc_type}
          </span>
        )}
      </div>

      {/* Starting → Ending state */}
      {(result.starting_state || result.ending_state) && (
        <div className="flex items-center gap-2 text-sm flex-wrap">
          {result.starting_state && (
            <span className="text-muted-foreground">{result.starting_state}</span>
          )}
          <ArrowRight className="h-4 w-4 shrink-0 text-[var(--color-accent)]" aria-hidden="true" />
          {result.ending_state && (
            <span className="font-medium text-[var(--color-text-primary)]">
              {result.ending_state}
            </span>
          )}
        </div>
      )}

      {/* Phases timeline */}
      {result.phases.length > 0 && <ArcPhasesTimeline phases={result.phases} />}

      {/* Key relationships */}
      {result.key_relationships.length > 0 && (
        <div className="flex flex-col gap-1">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("characterArc.keyRelationships")}
          </h4>
          <ul className="flex flex-col gap-0.5">
            {result.key_relationships.map((rel) => (
              <li key={rel} className="text-sm text-[var(--color-text-secondary)]">
                {rel}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Internal conflict */}
      {result.internal_conflict && (
        <div className="flex flex-col gap-1">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("characterArc.internalConflict")}
          </h4>
          <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
            {result.internal_conflict}
          </p>
        </div>
      )}

      {/* Resolution */}
      {result.resolution && (
        <div className="flex flex-col gap-1">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("characterArc.resolution")}
          </h4>
          <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
            {result.resolution}
          </p>
        </div>
      )}
    </div>
  );
}
