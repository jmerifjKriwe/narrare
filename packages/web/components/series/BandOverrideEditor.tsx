"use client";

/**
 * BandOverrideEditor — manual override editor for a novel's band summary
 * (Spec 2 — Series Generation Context, Task 8).
 *
 * Extracted from ``BandSummaryCard`` (RULE-04: modularize, don't compress).
 * Renders the override textarea plus:
 *
 * - Save → PATCH (``useUpdateBandSummaryOverride``), only while dirty.
 * - Clear Override → DELETE (``useClearBandSummaryOverride``), only when an
 *   override is active.
 *
 * The editor re-syncs its local text from the server while clean (mirrors
 * ``SeriesMetadataForm``). All copy via ``useTranslations("studio")`` under
 * ``series.bandSummary.*`` (none hardcoded).
 */
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import {
  useClearBandSummaryOverride,
  useUpdateBandSummaryOverride,
} from "@/lib/hooks/useBandSummary";

interface BandOverrideEditorProps {
  readonly seriesId: string;
  readonly novelId: string;
  readonly initialOverride: string | null;
}

export function BandOverrideEditor({
  seriesId,
  novelId,
  initialOverride,
}: BandOverrideEditorProps) {
  const t = useTranslations("studio");
  const updateOverride = useUpdateBandSummaryOverride(seriesId, novelId);
  const clearOverride = useClearBandSummaryOverride(seriesId, novelId);

  const [text, setText] = useState(initialOverride ?? "");
  const [dirty, setDirty] = useState(false);

  // Re-sync from server when the override changes externally (e.g. after a
  // background refetch), but only while clean (mirrors SeriesMetadataForm).
  useEffect(() => {
    if (dirty) return;
    setText(initialOverride ?? "");
  }, [initialOverride, dirty]);

  const hasOverride = initialOverride !== null && initialOverride.trim() !== "";

  return (
    <div className="space-y-2">
      <label className="text-xs font-medium text-foreground" htmlFor={`band-override-${novelId}`}>
        {t("series.bandSummary.override")}
      </label>
      <textarea
        id={`band-override-${novelId}`}
        data-testid="band-summary-override-input"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setDirty(true);
        }}
        rows={3}
        maxLength={5000}
        placeholder={t("series.bandSummary.overridePlaceholder")}
        className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <div className="flex items-center gap-2">
        {dirty ? (
          <button
            type="button"
            data-testid="band-summary-save-override"
            onClick={() => {
              updateOverride.mutate(text, { onSuccess: () => setDirty(false) });
            }}
            disabled={updateOverride.isPending || text.trim() === ""}
            className="rounded bg-primary px-3 py-1 text-xs text-primary-foreground disabled:opacity-50"
          >
            {t("series.bandSummary.saveOverride")}
          </button>
        ) : null}
        {hasOverride ? (
          <button
            type="button"
            data-testid="band-summary-clear-override"
            onClick={() => clearOverride.mutate()}
            disabled={clearOverride.isPending}
            className="text-xs text-destructive hover:underline disabled:opacity-50"
          >
            {t("series.bandSummary.clearOverride")}
          </button>
        ) : null}
      </div>
    </div>
  );
}
