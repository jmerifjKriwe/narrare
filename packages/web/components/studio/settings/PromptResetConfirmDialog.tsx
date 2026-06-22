"use client";

/**
 * PromptResetConfirmDialog — destructive-action confirmation for reset.
 *
 * Shows the current override side-by-side with the bundled default and
 * asks for explicit confirmation before calling ``onConfirm``. Mirrors the
 * styling of the existing :component:`PromptDiff` view (same two-column
 * diff layout) but is a focused confirmation, not a keep/accept choice.
 */

import { Loader2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect } from "react";

interface PromptResetConfirmDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly promptId: string;
  readonly overrideContent: string;
  readonly bundledContent: string;
  readonly onConfirm: () => void;
  readonly pending: boolean;
}

export function PromptResetConfirmDialog({
  open,
  onOpenChange,
  overrideContent,
  bundledContent,
  onConfirm,
  pending,
}: PromptResetConfirmDialogProps) {
  const t = useTranslations("studio");

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("settings.prompts.resetToDefault")}
        className="relative w-full max-w-3xl rounded-xl border border-border bg-card p-6 shadow-2xl"
      >
        <header className="mb-4 flex items-start justify-between gap-4">
          <h2 className="text-base font-medium text-foreground">
            {t("settings.prompts.resetToDefault")}
          </h2>
          <button
            type="button"
            aria-label={t("settings.prompts.promptCustomization.close")}
            onClick={() => onOpenChange(false)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <p className="mb-4 text-sm text-muted-foreground">{t("settings.prompts.confirmReset")}</p>

        <div className="mb-4 grid grid-cols-2 gap-4">
          <div>
            <h3 className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
              {t("settings.prompts.yourVersion")}
            </h3>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-2 font-mono text-xs">
              {overrideContent}
            </pre>
          </div>
          <div>
            <h3 className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
              {t("settings.prompts.newDefault")}
            </h3>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-2 font-mono text-xs">
              {bundledContent}
            </pre>
          </div>
        </div>

        <footer className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-md bg-muted px-4 py-2 text-sm hover:bg-accent"
          >
            {t("settings.prompts.cancel")}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={pending}
            className="flex items-center gap-2 rounded-md bg-destructive px-4 py-2 text-sm text-destructive-foreground hover:opacity-90 disabled:opacity-50"
          >
            {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {t("settings.prompts.resetToDefault")}
          </button>
        </footer>
      </div>
    </div>
  );
}
