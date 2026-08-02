"use client";

import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { listItemVariants } from "@/lib/motion-variants";
import type { SeriesSummary } from "@/types";

interface SeriesCardProps {
  /** Series to render (list-item shape from the dashboard query). */
  readonly series: SeriesSummary;
  /** Invoked with the series id when the card is clicked (navigation, etc.). */
  readonly onClick: (id: string) => void;
}

/**
 * Dashboard card for a Series (Spec 1, Slice 4, Task 4.4).
 *
 * Sits alongside standalone NovelCards in the mixed dashboard grid. It is
 * visually distinct via a blue accent so users can tell series from novels at
 * a glance. The whole card is one button element (fully keyboard-accessible)
 * that calls `onClick(id)`.
 *
 * Conventions matched to NovelCardGrid:
 *   - Entrance animation via `listItemVariants` from `@/lib/motion-variants`.
 *   - i18n under the shared `studio` namespace at `dashboard.series.*`.
 *   - `data-testid` marker on the interactive element (ui-principles §18).
 *   - Only phrasing content (spans) inside the button element — keeps the
 *     HTML valid (a button's content model is phrasing content, not flow).
 */
export function SeriesCard({ series, onClick }: SeriesCardProps) {
  const t = useTranslations("studio");

  return (
    <motion.button
      type="button"
      data-testid="series-card"
      variants={listItemVariants}
      onClick={() => onClick(series.id)}
      className="group relative block w-full rounded-lg border bg-accent-series-muted border-accent-series-border p-6 text-left transition-shadow hover:shadow-md"
    >
      <span className="mb-2 flex items-center gap-2">
        <span className="inline-block rounded-md bg-accent-series px-2 py-0.5 text-xs text-accent-series-foreground">
          {t("dashboard.series.badge")}
        </span>
        <span className="inline-block rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          {t(`dashboard.series.status.${series.status}`)}
        </span>
      </span>
      <span className="mb-1 block text-lg font-medium">{series.title}</span>
      {series.subtitle ? (
        <span className="mb-3 block text-sm text-muted-foreground">{series.subtitle}</span>
      ) : null}
      <span className="block text-xs text-muted-foreground">
        {t("dashboard.series.novel_count", { count: series.novel_count })}
      </span>
    </motion.button>
  );
}
