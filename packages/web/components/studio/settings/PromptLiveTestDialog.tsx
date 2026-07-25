"use client";

/**
 * PromptLiveTestDialog — optional provider-/secret-gated SSE live test.
 *
 * The dialog is render-only: the parent (``usePromptEditorState``) owns the
 * ``useAIOperation`` lifecycle, the streamed ``output``, the
 * ``acknowledged`` flag, and any structured ``error``. This keeps the
 * transport + state-machine concerns in the hook and the visual layer in
 * the component (RULE-04).
 *
 * Phase 1 — warning gate: shows the token/privacy warning and requires the
 *   user to click ``confirmRun`` before any request is fired.
 * Phase 2 — output: shows the streamed text with cancel + retry controls.
 *
 * §16 compliance:
 *   - lifecycle: parent-owned useAIOperation (cancel/retry/state).
 *   - error mapping: structured ``error`` prop carries an i18n key.
 *   - i18n: all visible strings via ``studio.settings.prompts.promptCustomization.*``.
 */

import { Loader2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { dialogVariants, overlayVariants } from "@/lib/motion-variants";

interface PromptLiveTestDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly promptId: string;
  /** True after the user acknowledged the token/privacy warning. */
  readonly acknowledged: boolean;
  /** Streamed output text accumulated so far. */
  readonly output: string;
  /** True while the SSE stream is active. */
  readonly streaming: boolean;
  /** Structured error i18n key from mapSSEError, or null. */
  readonly error: string | null;
  /** Fire the live test (called when the warning is acknowledged). */
  readonly onConfirm: () => void;
  /** Cancel the in-flight stream. */
  readonly onCancel: () => void;
  /** Retry after an error (optional — parent may reuse onConfirm). */
  readonly onRetry?: () => void;
}

export function PromptLiveTestDialog({
  open,
  onOpenChange,
  acknowledged,
  output,
  streaming,
  error,
  onConfirm,
  onCancel,
  onRetry,
}: PromptLiveTestDialogProps) {
  const t = useTranslations("studio");

  // Escape closes (or cancels the stream if active).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (streaming) onCancel();
        onOpenChange(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, streaming, onCancel, onOpenChange]);

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
            onClick={() => {
              if (streaming) onCancel();
              onOpenChange(false);
            }}
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
            aria-label={t("settings.prompts.promptCustomization.testTitle")}
            className="relative flex max-h-[85vh] w-full max-w-3xl flex-col rounded-xl border border-border bg-card p-6 shadow-2xl"
          >
            <header className="mb-4 flex items-start justify-between gap-4">
              <h2 className="text-base font-medium text-foreground">
                {t("settings.prompts.promptCustomization.testTitle")}
              </h2>
              <button
                type="button"
                aria-label={t("settings.prompts.promptCustomization.close")}
                onClick={() => {
                  if (streaming) onCancel();
                  onOpenChange(false);
                }}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </header>

            {!acknowledged ? (
              <section
                className="mb-4 rounded-md border border-amber-500/40 bg-amber-500/10 p-4 text-sm"
                aria-label={t("settings.prompts.promptCustomization.tokenWarning")}
              >
                <p className="text-foreground">
                  {t("settings.prompts.promptCustomization.tokenWarning")}
                </p>
                <button
                  type="button"
                  onClick={onConfirm}
                  className="mt-3 rounded-md bg-amber-500/20 px-3 py-1.5 text-sm hover:bg-amber-500/30"
                >
                  {t("settings.prompts.promptCustomization.confirmRun")}
                </button>
              </section>
            ) : (
              <section className="flex-1 overflow-y-auto pr-1">
                <pre
                  className="min-h-[200px] whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-sm"
                  aria-live="polite"
                >
                  {output ||
                    (streaming ? "…" : t("settings.prompts.promptCustomization.testEmpty"))}
                </pre>
                {error && (
                  <p role="alert" className="mt-2 text-sm text-destructive">
                    {t(`settings.prompts.promptCustomization.${error}`)}
                  </p>
                )}
                <div className="mt-3 flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={onCancel}
                    disabled={!streaming}
                    className="rounded-md bg-muted px-4 py-2 text-sm hover:bg-accent disabled:opacity-50"
                  >
                    {t("aiActions.stop")}
                  </button>
                  <button
                    type="button"
                    onClick={onRetry ?? onConfirm}
                    disabled={streaming}
                    className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50"
                  >
                    {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    {t("aiActions.retry")}
                  </button>
                </div>
              </section>
            )}

            <footer className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  if (streaming) onCancel();
                  onOpenChange(false);
                }}
                className="rounded-md bg-muted px-4 py-2 text-sm hover:bg-accent"
              >
                {t("settings.prompts.promptCustomization.close")}
              </button>
            </footer>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
