"use client";

/**
 * BaendeList — the "Bände" tab body: the ordered list of novels in a Series
 * (Spec 1, Slice 4, Task 4.7).
 *
 * Fetches the series novels via `seriesApi.listNovels` (already ordered by
 * `series_position` server-side) and renders one row per novel with a 1-based
 * position pill, a link to the novel, an `is_demo` badge, and up/down reorder
 * controls (PATCH `seriesApi.reorderNovels` with the full swapped id list). The
 * "Add Novel" join flow is delegated to `AddNovelToSeries`.
 *
 * RULE-04: the row is a focused inline sub-component (`BaendeNovelRow`); the
 * list owns data + reorder. All copy goes through `useTranslations("studio")`
 * under `series.baende.*` (keys added by Task 4.9; none hardcoded).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { Route } from "next";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { seriesApi } from "@/lib/api/series";
import { seriesKeys } from "@/lib/hooks/seriesKeys";
import { listContainerVariants, listItemVariants } from "@/lib/motion-variants";
import type { NovelSummary } from "@/types";
import { AddNovelToSeries } from "./AddNovelToSeries";

interface BaendeListProps {
  readonly seriesId: string;
}

export function BaendeList({ seriesId }: BaendeListProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();

  const { data: novels = [], isLoading } = useQuery({
    queryKey: seriesKeys.novels(seriesId),
    queryFn: () => seriesApi.listNovels(seriesId),
  });

  const reorder = useMutation({
    mutationFn: (novelIds: string[]) => seriesApi.reorderNovels(seriesId, novelIds),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.novels(seriesId) });
    },
  });

  function handleReorderUp(index: number): void {
    if (index <= 0) return;
    const ids = novels.map((novel) => novel.id);
    [ids[index - 1], ids[index]] = [ids[index], ids[index - 1]];
    reorder.mutate(ids);
  }

  function handleReorderDown(index: number): void {
    if (index >= novels.length - 1) return;
    const ids = novels.map((novel) => novel.id);
    [ids[index], ids[index + 1]] = [ids[index + 1], ids[index]];
    reorder.mutate(ids);
  }

  if (isLoading) {
    return (
      <div
        data-testid="baende-list-loading"
        className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground"
      >
        <Loader2 className="h-5 w-5 animate-spin" />
        {t("series.baende.loading")}
      </div>
    );
  }

  return (
    <section data-testid="baende-list" className="max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-medium">{t("series.baende.title")}</h2>
        <AddNovelToSeries
          seriesId={seriesId}
          nextPosition={novels.length + 1}
          onAdded={() => {
            void queryClient.invalidateQueries({ queryKey: seriesKeys.novels(seriesId) });
          }}
        />
      </div>

      {novels.length === 0 ? (
        <p
          data-testid="baende-list-empty"
          className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground"
        >
          {t("series.baende.empty")}
        </p>
      ) : (
        <motion.ul
          variants={listContainerVariants}
          initial="hidden"
          animate="visible"
          className="space-y-2"
        >
          <AnimatePresence initial={false}>
            {novels.map((novel, index) => (
              <BaendeNovelRow
                key={novel.id}
                novel={novel}
                index={index}
                total={novels.length}
                onReorderUp={() => handleReorderUp(index)}
                onReorderDown={() => handleReorderDown(index)}
              />
            ))}
          </AnimatePresence>
        </motion.ul>
      )}
    </section>
  );
}

// --- Single novel row --------------------------------------------------------

interface BaendeNovelRowProps {
  readonly novel: NovelSummary;
  readonly index: number;
  readonly total: number;
  readonly onReorderUp: () => void;
  readonly onReorderDown: () => void;
}

function BaendeNovelRow({ novel, index, total, onReorderUp, onReorderDown }: BaendeNovelRowProps) {
  const t = useTranslations("studio");

  return (
    <motion.li
      variants={listItemVariants}
      data-testid="baende-novel-row"
      className="flex items-center gap-3 rounded-lg border border-border bg-card p-3"
    >
      <span
        data-testid={`baende-position-${index}`}
        className="inline-flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-medium text-white"
      >
        {index + 1}
      </span>
      <Link
        href={`/novel/${novel.id}` as Route}
        className="flex-1 truncate font-medium text-foreground hover:underline"
      >
        {novel.title}
      </Link>
      {novel.is_demo ? (
        <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
          {t("series.baende.demoBadge")}
        </span>
      ) : null}
      <div className="flex flex-shrink-0 items-center gap-1">
        <button
          type="button"
          onClick={onReorderUp}
          disabled={index === 0}
          title={t("series.baende.reorderUp")}
          aria-label={t("series.baende.reorderUp")}
          className="rounded p-1.5 hover:bg-accent disabled:opacity-30"
        >
          <ChevronUp className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onReorderDown}
          disabled={index === total - 1}
          title={t("series.baende.reorderDown")}
          aria-label={t("series.baende.reorderDown")}
          className="rounded p-1.5 hover:bg-accent disabled:opacity-30"
        >
          <ChevronDown className="h-4 w-4" />
        </button>
      </div>
    </motion.li>
  );
}
