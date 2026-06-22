"use client";

/**
 * PromptPreviewDialog — modal showing the provider-free resolved prompt.
 *
 * Renders the result of ``POST /api/v1/prompts/{prompt_id}/preview``: the
 * cascade-resolved system/user prompt, the variable governance table, and
 * any diagnostics (missing variables, validation notes).
 *
 * The dialog is purely presentational — it receives ``preview`` and
 * ``loading`` from the parent (which drives the query via the
 * ``usePromptEditorState`` hook).
 *
 * Implementation note: uses the same simple ``role="dialog"`` modal pattern
 * as :component:`ToneFormDialog` — no extra Radix dependency.
 */

import { Loader2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import type { PromptPreview } from "@/types";
import { VariableMetadataPanel } from "./VariableMetadataPanel";

interface PromptPreviewDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly promptId: string;
  readonly preview: PromptPreview | null;
  readonly loading: boolean;
}

export function PromptPreviewDialog({
  open,
  onOpenChange,
  preview,
  loading,
}: PromptPreviewDialogProps) {
  const t = useTranslations("studio");

  // Close on Escape — follows the same pattern as ToneFormDialog.
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
        aria-label={t("settings.prompts.promptCustomization.previewTitle")}
        className="relative flex max-h-[85vh] w-full max-w-3xl flex-col rounded-xl border border-border bg-card p-6 shadow-2xl"
      >
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-medium text-foreground">
              {t("settings.prompts.promptCustomization.previewTitle")}
            </h2>
            {preview && (
              <p className="mt-1 text-xs text-muted-foreground">
                {t("settings.prompts.promptCustomization.cascadeSource")}:
                <span className="ml-1 font-mono">{preview.cascade_source}</span>
              </p>
            )}
          </div>
          <button
            type="button"
            aria-label={t("settings.prompts.promptCustomization.close")}
            onClick={() => onOpenChange(false)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        {loading || !preview ? (
          <div className="flex items-center justify-center py-12" role="status">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">
              {t("settings.prompts.promptCustomization.loading")}
            </span>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto pr-1">
            <section className="mb-4">
              <h3 className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
                {t("settings.prompts.promptCustomization.resolvedSystem")}
              </h3>
              <pre className="whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-sm">
                {preview.system_prompt || t("settings.prompts.promptCustomization.emptyResolution")}
              </pre>
            </section>

            {preview.user_prompt && (
              <section className="mb-4">
                <h3 className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
                  {t("settings.prompts.promptCustomization.resolvedUser")}
                </h3>
                <pre className="whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-sm">
                  {preview.user_prompt}
                </pre>
              </section>
            )}

            {preview.first_message !== null && (
              <section className="mb-4">
                <h3 className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
                  {t("settings.prompts.promptCustomization.resolvedFirstMessage")}
                </h3>
                <pre className="whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-sm">
                  {preview.first_message ||
                    t("settings.prompts.promptCustomization.emptyResolution")}
                </pre>
              </section>
            )}

            <section className="mb-4">
              <h3 className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
                {t("settings.prompts.promptCustomization.variables")}
              </h3>
              <VariableMetadataPanel variables={preview.variables} />
            </section>

            {preview.diagnostics.length > 0 && (
              <section
                className="mb-4"
                aria-label={t("settings.prompts.promptCustomization.diagnostics")}
              >
                <h3 className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
                  {t("settings.prompts.promptCustomization.diagnostics")}
                </h3>
                <ul className="space-y-1 text-sm">
                  {preview.diagnostics.map((d) => (
                    <li
                      key={`${d.kind}:${d.variable_name ?? "(none)"}:${d.message}`}
                      className="text-amber-700 dark:text-amber-300"
                    >
                      {`[${d.kind}] ${d.variable_name ?? "-"}: ${d.message}`}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}

        <footer className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-md bg-muted px-4 py-2 text-sm hover:bg-accent"
          >
            {t("settings.prompts.promptCustomization.close")}
          </button>
        </footer>
      </div>
    </div>
  );
}
