"use client";

import { BookOpen, Plus } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { SeriesCard } from "@/components/dashboard/SeriesCard";
import { crossfadeVariants, listContainerVariants } from "@/lib/motion-variants";
import type { NovelSummary, SeriesSummary } from "@/types";
import { NovelCard } from "./NovelCard";

/**
 * DashboardLibrary — the N2 mixed grid of Series cards + standalone Novel
 * cards (Spec 1, Slice 4, Task 4.5).
 *
 * Replaces the former NovelCardGrid as the dashboard's library surface. It:
 *   - receives the full novels list and keeps only standalone novels
 *     (`series_id` falsy) so novels that belong to a series are not duplicated
 *     here (they are reached via their SeriesCard),
 *   - renders SeriesCards (blue accent) and NovelCards together in one
 *     responsive grid,
 *   - always offers the "New Series" and "New Novel" entry points (even when
 *     the library is empty, so the user can create their first item),
 *   - shows a combined loading skeleton while data is loading and a combined
 *     empty hint when there is nothing yet.
 *
 * Conventions matched to the former NovelCardGrid: same grid classes, same
 * motion variants (crossfade for state transitions, staggered list items),
 * same `data-testid` markers (`novel-card`, `new-novel-btn`) plus the new
 * `new-series-btn`. i18n lives under `studio.dashboard.*` (the `dashboard.series`
 * keys are added in Task 4.9; until then the keys render verbatim).
 */
export interface DashboardLibraryProps {
  readonly series: SeriesSummary[];
  readonly novels: NovelSummary[];
  readonly isLoading: boolean;
  readonly onOpenSeries: (id: string) => void;
  readonly onNewSeries: () => void;
  readonly onDeleteNovel: (id: string, title: string) => void;
  readonly onEditNovel: (id: string) => void;
  readonly onExportNovel: (id: string) => void;
  readonly onNewNovel: () => void;
  readonly isDeleting: boolean;
  readonly formatDate: (dateStr: string) => string;
}

export function DashboardLibrary({
  series,
  novels,
  isLoading,
  onOpenSeries,
  onNewSeries,
  onDeleteNovel,
  onEditNovel,
  onExportNovel,
  onNewNovel,
  isDeleting,
  formatDate,
}: DashboardLibraryProps) {
  const t = useTranslations("studio");

  // Standalone novels only — novels that belong to a series are reached via
  // their SeriesCard, not duplicated here.
  const standaloneNovels = novels.filter((n) => !n.series_id);
  const isEmpty = series.length === 0 && standaloneNovels.length === 0;

  return (
    <AnimatePresence mode="wait">
      {isLoading ? (
        <motion.div
          key="skeleton"
          variants={crossfadeVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
        >
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-card border border-border rounded-lg p-6 animate-pulse">
              <div className="h-6 bg-muted rounded mb-2 w-3/4" />
              <div className="h-4 bg-muted rounded mb-4 w-1/2" />
              <div className="h-4 bg-muted rounded w-1/3" />
            </div>
          ))}
        </motion.div>
      ) : (
        <motion.div
          key="content"
          variants={crossfadeVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
        >
          {isEmpty ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <BookOpen className="w-12 h-12 mb-3 opacity-10" />
              <p className="text-lg mb-1">{t("dashboard.emptyTitle")}</p>
              <p className="text-sm">{t("dashboard.emptySubtitle")}</p>
            </div>
          ) : null}

          <motion.div
            variants={listContainerVariants}
            initial="hidden"
            animate="visible"
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
          >
            {series.map((s) => (
              <SeriesCard key={s.id} series={s} onClick={onOpenSeries} />
            ))}

            {standaloneNovels.map((novel) => (
              <NovelCard
                key={novel.id}
                novel={novel}
                formatDate={formatDate}
                onDelete={onDeleteNovel}
                onEdit={onEditNovel}
                onExport={onExportNovel}
                isDeleting={isDeleting}
              />
            ))}

            {/* New Series card — tinted with the Series accent token */}
            <button
              type="button"
              data-testid="new-series-btn"
              onClick={onNewSeries}
              className="flex flex-col items-center justify-center bg-accent-series-muted border-2 border-dashed border-accent-series-border rounded-lg p-6 hover:border-accent-series hover:bg-accent-series-muted/60 transition-colors min-h-[180px]"
            >
              <div className="w-10 h-10 rounded-full bg-accent-series-muted flex items-center justify-center mb-3">
                <Plus className="w-5 h-5 text-accent-series-muted-foreground" />
              </div>
              <span className="text-sm font-medium text-accent-series-muted-foreground">
                {t("dashboard.series.new_series")}
              </span>
            </button>

            {/* New Novel card — unchanged from the former NovelCardGrid */}
            <button
              type="button"
              data-testid="new-novel-btn"
              onClick={onNewNovel}
              className="flex flex-col items-center justify-center bg-card border-2 border-dashed border-border rounded-lg p-6 hover:border-primary/50 hover:bg-accent transition-colors min-h-[180px]"
            >
              <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-3">
                <Plus className="w-5 h-5 text-muted-foreground" />
              </div>
              <span className="text-sm font-medium text-muted-foreground">
                {t("dashboard.newNovel")}
              </span>
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
