"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

/**
 * NewSeriesDialog — minimal accessible create-series dialog
 * (Spec 1, Slice 4, Task 4.5).
 *
 * This is the basic Spec-1 "New Series" entry point: a single title field with
 * Create / Cancel actions. On Create it calls `onCreate(trimmedTitle)`; the
 * parent owns the create mutation and closes the dialog on success.
 *
 * Implementation notes:
 *   - Dependency-free. `@radix-ui/react-dialog` is not installed in this
 *     project, and adding a dependency for a Spec-1 placeholder is out of
 *     scope (and out of this layer's authority). A plain `role="dialog"`
 *     overlay + panel gives correct semantics (NOT alert semantics — this is a
 *     form, not a confirmation).
 *   - Escape closes; overlay click closes; the title input auto-focuses.
 *   - i18n keys live under `studio.dashboard.series.*` and are added in
 *     Task 4.9; until then they render verbatim (matching SeriesCard).
 */
export interface NewSeriesDialogProps {
  /** Controlled open state. */
  readonly open: boolean;
  /** Called with `false` when the dialog should close (escape, overlay, cancel). */
  readonly onOpenChange: (open: boolean) => void;
  /** Called with the trimmed title when the user confirms creation. */
  readonly onCreate: (title: string) => void;
  /** Disables the Create button while the create mutation is in flight. */
  readonly isCreating?: boolean;
}

export function NewSeriesDialog({
  open,
  onOpenChange,
  onCreate,
  isCreating = false,
}: NewSeriesDialogProps) {
  const t = useTranslations("studio");
  const [title, setTitle] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset the field whenever the dialog closes so a reopen starts empty.
  useEffect(() => {
    if (!open) setTitle("");
  }, [open]);

  // Autofocus the title field when the dialog opens.
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  if (!open) return null;

  const trimmed = title.trim();
  const canCreate = trimmed.length > 0 && !isCreating;

  function handleClose() {
    onOpenChange(false);
  }

  function handleCreate() {
    if (!canCreate) return;
    onCreate(trimmed);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop — a real button so the click target is an interactive element
          (lint-clean) and keyboard/AT users get a labelled way to dismiss. */}
      <button
        type="button"
        aria-label={t("dashboard.series.cancel")}
        tabIndex={-1}
        onClick={handleClose}
        className="absolute inset-0 cursor-default bg-black/50 backdrop-blur-sm"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-series-dialog-title"
        onKeyDown={(e) => {
          if (e.key === "Escape") handleClose();
        }}
        className="relative z-10 w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl"
      >
        <h2 id="new-series-dialog-title" className="text-lg font-medium text-foreground">
          {t("dashboard.series.create_title")}
        </h2>

        <div className="mt-4">
          <label
            htmlFor="new-series-title"
            className="block text-sm font-medium text-foreground mb-1"
          >
            {t("dashboard.series.title_label")}
          </label>
          <input
            ref={inputRef}
            id="new-series-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && canCreate) handleCreate();
            }}
            placeholder={t("dashboard.series.title_placeholder")}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            data-testid="new-series-cancel"
            onClick={handleClose}
            className="rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground hover:bg-accent transition-colors"
          >
            {t("dashboard.series.cancel")}
          </button>
          <button
            type="button"
            data-testid="new-series-create"
            onClick={handleCreate}
            disabled={!canCreate}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("dashboard.series.create_label")}
          </button>
        </div>
      </div>
    </div>
  );
}
