"use client";

/**
 * JoinPreviewDialog — controlled, presentational preview of a Series Join
 * (Spec 1, Slice 4, Task 4.8; Policy α — preview-then-apply).
 *
 * Renders a fetched `JoinPreview` (the per-entry treatment list the backend
 * computes for joining a novel into a series) and asks the user to confirm
 * applying the join. It owns NO data fetching — the parent (`AddNovelToSeries`)
 * drives `useJoinPreview` / `useApplyJoin` and passes state in via props,
 * mirroring the `ConfirmDialog` controlled-component pattern.
 *
 * Each treatment is shown as: `slug` · entity-type · → target · reason. The
 * explanation copy switches on `canon_empty` (promote-everything vs
 * promote-unique / keep-duplicates). All copy goes through
 * `useTranslations("studio")` under `series.join.*` — no hardcoded JSX text
 * (enforced by scripts/validate-i18n.ts; keys added by Task 4.9).
 */
import { Loader2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { dialogVariants, overlayVariants } from "@/lib/motion-variants";
import type { JoinPreview } from "@/types";
import { JoinTreatmentRow } from "./JoinTreatmentRow";

interface JoinPreviewDialogProps {
  /** Controlled open state. */
  readonly open: boolean;
  /** Called with `false` on backdrop click / close / cancel. */
  readonly onOpenChange: (open: boolean) => void;
  /** Novel being joined — shown in the dialog title. */
  readonly novelTitle: string;
  /** The fetched preview, or `null` while loading / on error. */
  readonly preview: JoinPreview | null;
  readonly isLoading: boolean;
  readonly isError: boolean;
  /** Disable confirm + show spinner while the join is being applied. */
  readonly isApplying: boolean;
  readonly applyError: boolean;
  /** Called when the user confirms — parent runs `applyJoin`. */
  readonly onConfirm: () => void;
}

export function JoinPreviewDialog({
  open,
  onOpenChange,
  novelTitle,
  preview,
  isLoading,
  isError,
  isApplying,
  applyError,
  onConfirm,
}: JoinPreviewDialogProps) {
  const t = useTranslations("studio");
  const close = () => onOpenChange(false);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="fixed inset-0 z-50 flex items-center justify-center"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={close}
            aria-hidden="true"
          />

          {/* Dialog */}
          <motion.div
            variants={dialogVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            role="dialog"
            aria-modal="true"
            aria-label={t("series.join.title", { novel: novelTitle })}
            data-testid="join-preview-dialog"
            className="relative w-full max-w-xl rounded-xl border border-border bg-card p-6 shadow-2xl"
          >
            <header className="mb-4 flex items-start justify-between gap-4">
              <h2 className="text-base font-medium text-foreground">
                {t("series.join.title", { novel: novelTitle })}
              </h2>
              <button
                type="button"
                aria-label={t("series.join.close")}
                onClick={close}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </header>

            <JoinPreviewBody
              preview={preview}
              isLoading={isLoading}
              isError={isError}
              applyError={applyError}
            />

            <footer className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                data-testid="join-preview-cancel"
                onClick={close}
                className="rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground hover:bg-accent"
              >
                {t("series.join.cancel")}
              </button>
              <button
                type="button"
                data-testid="join-preview-confirm"
                onClick={onConfirm}
                disabled={isApplying || isLoading || isError || !preview}
                className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {isApplying ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {t("series.join.confirm")}
              </button>
            </footer>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// --- Body (loading / error / treatments) -------------------------------------

interface JoinPreviewBodyProps {
  readonly preview: JoinPreview | null;
  readonly isLoading: boolean;
  readonly isError: boolean;
  readonly applyError: boolean;
}

function JoinPreviewBody({ preview, isLoading, isError, applyError }: JoinPreviewBodyProps) {
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
        {preview.treatments.map((treatment) => (
          <JoinTreatmentRow key={treatment.entry_id} treatment={treatment} />
        ))}
      </ul>
      {applyError ? (
        <p className="text-sm text-destructive">{t("series.join.applyError")}</p>
      ) : null}
    </div>
  );
}
