"use client";

/**
 * JoinPreviewBody — the preview content rendered inside JoinPreviewDialog
 * (Spec 1, Slice 4, Task 4.8; Policy α — preview-then-apply).
 *
 * Extracted from JoinPreviewDialog (RULE-04: one responsibility per file) so
 * the dialog stays a thin composition/behavior shell (overlay, close-gating,
 * confirm/cancel footer) while this component owns the preview-content states:
 * loading, error, and the fetched treatment list.
 *
 * Each treatment is rendered by JoinTreatmentRow. The list includes an
 * empty-treatments branch (m6 review-fix): when `preview.treatments` is empty,
 * a friendly message (`series.join.noTreatments`) is shown instead of an empty
 * bordered box. All copy goes through `useTranslations("studio")` under
 * `series.join.*` — no hardcoded JSX text (enforced by scripts/validate-i18n.ts).
 */
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { JoinPreview } from "@/types";
import { JoinTreatmentRow } from "./JoinTreatmentRow";

interface JoinPreviewBodyProps {
  /** The fetched preview, or `null` while loading / on error. */
  readonly preview: JoinPreview | null;
  readonly isLoading: boolean;
  readonly isError: boolean;
  readonly applyError: boolean;
}

export function JoinPreviewBody({ preview, isLoading, isError, applyError }: JoinPreviewBodyProps) {
  const t = useTranslations("studio");

  if (isLoading) {
    return (
      <div
        data-testid="join-preview-loading"
        className="flex items-center gap-2 py-6 text-sm text-muted-foreground"
      >
        <Loader2 className="h-4 w-4 animate-spin" />
        {t("series.join.loading")}
      </div>
    );
  }

  if (isError) {
    return (
      <p data-testid="join-preview-error" className="py-6 text-sm text-destructive">
        {t("series.join.previewError")}
      </p>
    );
  }

  if (!preview) return null;

  const explanationKey = preview.canon_empty
    ? "series.join.explanation.canon_empty"
    : "series.join.explanation.canon_nonempty";

  return (
    <div className="space-y-3">
      <p data-testid="join-preview-explanation" className="text-sm text-muted-foreground">
        {t(explanationKey)}
      </p>
      <ul className="divide-y divide-border rounded-md border border-border">
        {preview.treatments.length === 0 ? (
          <li data-testid="join-preview-empty" className="px-4 py-3 text-sm text-muted-foreground">
            {t("series.join.noTreatments")}
          </li>
        ) : (
          preview.treatments.map((treatment) => (
            <JoinTreatmentRow key={treatment.entry_id} treatment={treatment} />
          ))
        )}
      </ul>
      {applyError ? (
        <p className="text-sm text-destructive">{t("series.join.applyError")}</p>
      ) : null}
    </div>
  );
}
