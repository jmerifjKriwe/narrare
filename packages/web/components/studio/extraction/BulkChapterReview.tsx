"use client";

/**
 * BulkChapterReview — per-chapter review body of the BulkExtractionPanel
 * (F2 T7, ADR-092 spec §8.2).
 *
 * Reuses the single-chapter review stack verbatim: `ExtractionReview` with
 * `ExtractionItemCard` underneath and the `useExtractionSelection` selection
 * state (confidence-sorted, preselected). Apply goes through the EXISTING
 * `useApplyExtraction` hook → existing `POST /kb/extract/apply` endpoint,
 * passing this chapter's id so ADR-085 provenance stamps the source chapter
 * (non-LLM apply, never auto-applied).
 *
 * @module BulkChapterReview
 */

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import type { ExtractionOutput } from "@/lib/api/extraction";
import { useApplyExtraction } from "@/lib/hooks/useExtraction";
import { useExtractionSelection } from "@/lib/hooks/useExtractionSelection";
import { ExtractionReview } from "./ExtractionReview";
import { getErrorMessage, isAbortError, mapSelectedItems } from "./extraction-utils";

interface BulkChapterReviewProps {
  readonly novelId: string;
  /** The chapter under review — stamps `chapter_id` on the apply request. */
  readonly chapterId: string;
  /** Full extraction output of this chapter (results endpoint, state done). */
  readonly output: ExtractionOutput;
  /** Called after a successful apply (panel marks the chapter applied). */
  readonly onApplied: (chapterId: string) => void;
  /** Called when the user skips this chapter (panel marks it skipped). */
  readonly onSkipped: (chapterId: string) => void;
}

export function BulkChapterReview({
  novelId,
  chapterId,
  output,
  onApplied,
  onSkipped,
}: BulkChapterReviewProps) {
  const t = useTranslations("studio");
  const selection = useExtractionSelection();
  const applyMutation = useApplyExtraction(novelId, chapterId);
  const [applyError, setApplyError] = useState<string | null>(null);

  // Load this chapter's output into the shared selection state (sorted by
  // confidence, all items preselected) whenever another chapter's output
  // becomes the active one.
  // biome-ignore lint/correctness/useExhaustiveDependencies: output identity drives the reload; the selection setters are stable
  useEffect(() => {
    selection.loadResults(output);
  }, [output]);

  const handleApply = () => {
    const selected = mapSelectedItems(selection.items, selection.selectedIndices);
    applyMutation
      .mutateAsync(selected)
      .then(() => onApplied(chapterId))
      .catch((err: unknown) => {
        if (isAbortError(err)) return;
        setApplyError(getErrorMessage(err, t("kb.extractionApplyError")));
      });
  };

  return (
    <div className="space-y-4">
      <ExtractionReview
        items={selection.items}
        selectedIndices={selection.selectedIndices}
        onToggleItem={selection.toggleItem}
        onSelectAll={selection.selectAll}
        onSelectNone={selection.selectNone}
        analysisNotes={selection.analysisNotes}
      />

      {applyError && (
        <p role="alert" className="text-sm text-destructive">
          {applyError}
        </p>
      )}

      <div className="flex items-center justify-between border-t border-border pt-4">
        <span className="text-sm text-muted-foreground">
          {t("kb.extractionSelectedSummary", {
            count: selection.selectedIndices.size,
            total: selection.items.length,
          })}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onSkipped(chapterId)}
            className="px-3 py-2 text-sm rounded-md border border-border hover:bg-accent transition-colors"
          >
            {t("kb.bulkExtraction.skip")}
          </button>
          <button
            type="button"
            onClick={handleApply}
            disabled={selection.selectedIndices.size === 0 || applyMutation.isPending}
            className="px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {applyMutation.isPending
              ? t("kb.extractionApplying")
              : t("kb.bulkExtraction.applyForChapter")}
          </button>
        </div>
      </div>
    </div>
  );
}
