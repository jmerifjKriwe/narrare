"use client";

/**
 * AddNovelToSeries — orchestrates the "Add Novel" join flow for the Bände list
 * (Spec 1, Slice 4, Task 4.7/4.8; Policy α — preview-then-apply).
 *
 * Composes the presentational `JoinPreviewDialog`. Responsibilities:
 *   - Fetch all novels and filter to standalone ones (`series_id === null`),
 *     i.e. the novels eligible to be joined into a series.
 *   - Let the user pick one from a dropdown and click "Add Novel".
 *   - Preview the join via `useJoinPreview` (non-mutating), then open the dialog.
 *   - On confirm, apply via `useApplyJoin` at the supplied `nextPosition`
 *     (1-based append slot), then close + reset + call `onAdded`.
 *
 * The novel picker is intentionally minimal (a native select) — the dialog is
 * the spec'd deliverable. All copy goes through `useTranslations("studio")`
 * under `series.baende.*` / `series.join.*` (keys added by Task 4.9).
 */
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { novelsApi } from "@/lib/api/client";
import { useApplyJoin, useJoinPreview } from "@/lib/hooks/useSeriesJoin";
import { JoinPreviewDialog } from "./JoinPreviewDialog";

interface AddNovelToSeriesProps {
  readonly seriesId: string;
  /** 1-based slot the joined novel will occupy (append = current count + 1). */
  readonly nextPosition: number;
  /** Called after a successful apply (e.g. to refetch the novels list). */
  readonly onAdded?: () => void;
}

export function AddNovelToSeries({ seriesId, nextPosition, onAdded }: AddNovelToSeriesProps) {
  const t = useTranslations("studio");
  const [selectedNovelId, setSelectedNovelId] = useState("");
  const [open, setOpen] = useState(false);

  const { data: allNovels = [] } = useQuery({
    queryKey: ["novels"],
    queryFn: () => novelsApi.list(),
  });
  const standalone = allNovels.filter((novel) => novel.series_id === null);
  const selectedNovel = standalone.find((novel) => novel.id === selectedNovelId) ?? null;

  const preview = useJoinPreview(seriesId);
  const apply = useApplyJoin(seriesId);

  async function handleAdd(): Promise<void> {
    if (!selectedNovelId) return;
    await preview.mutateAsync(selectedNovelId);
    setOpen(true);
  }

  async function handleConfirm(): Promise<void> {
    if (!selectedNovelId) return;
    await apply.mutateAsync({ novelId: selectedNovelId, position: nextPosition });
    onAdded?.();
    setOpen(false);
    setSelectedNovelId("");
  }

  const noCandidates = standalone.length === 0;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {noCandidates ? (
        <span data-testid="add-novel-empty" className="text-sm text-muted-foreground">
          {t("series.baende.noStandaloneNovels")}
        </span>
      ) : (
        <select
          data-testid="add-novel-select"
          value={selectedNovelId}
          onChange={(e) => setSelectedNovelId(e.target.value)}
          aria-label={t("series.baende.addNovel")}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="">{t("series.baende.selectNovel")}</option>
          {standalone.map((novel) => (
            <option key={novel.id} value={novel.id}>
              {novel.title}
            </option>
          ))}
        </select>
      )}

      <button
        type="button"
        data-testid="add-novel-to-series"
        onClick={handleAdd}
        disabled={noCandidates || !selectedNovelId}
        className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        <Plus className="h-4 w-4" />
        {t("series.baende.addNovel")}
      </button>

      <JoinPreviewDialog
        open={open}
        onOpenChange={setOpen}
        novelTitle={selectedNovel?.title ?? ""}
        preview={preview.data ?? null}
        isLoading={preview.isPending}
        isError={preview.isError}
        isApplying={apply.isPending}
        applyError={apply.isError}
        onConfirm={handleConfirm}
      />
    </div>
  );
}
