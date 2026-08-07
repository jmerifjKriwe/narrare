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
import { useRef } from "react";
import { useDialogFocus } from "@/lib/hooks/use-dialog-focus";
import { dialogVariants, overlayVariants } from "@/lib/motion-variants";
import type { JoinPreview } from "@/types";
import { JoinPreviewBody } from "./JoinPreviewBody";

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
  // Don't allow dismissal mid-mutation: gating `close` on `!isApplying` covers
  // the backdrop click, the X button, the cancel button, and Escape
  // (`useDialogFocus` reads `onClose` through a ref, so the latest guarded
  // callback is always used) — a user can't lose the applying spinner or
  // re-trigger the join by dismissing the dialog while a request is in flight.
  const close = () => {
    if (!isApplying) onOpenChange(false);
  };
  const dialogRef = useRef<HTMLDivElement>(null);
  // I-F4: modal focus lifecycle — focus on open, ESC close, Tab trap, return
  // focus to the opener on close.
  useDialogFocus({ open, dialogRef, onClose: close });

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
            ref={dialogRef}
            variants={dialogVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            role="dialog"
            aria-modal="true"
            aria-labelledby="join-preview-dialog-title"
            tabIndex={-1}
            data-testid="join-preview-dialog"
            className="relative w-full max-w-xl rounded-xl border border-border bg-card p-6 shadow-2xl"
          >
            <header className="mb-4 flex items-start justify-between gap-4">
              <h2 id="join-preview-dialog-title" className="text-base font-medium text-foreground">
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
