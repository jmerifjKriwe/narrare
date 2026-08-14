"use client";

import { useTranslations } from "next-intl";
import type { ExportOptions } from "@/types";

/**
 * EpubOptionsGroup — the EPUB-only options fieldset (cover image path,
 * custom CSS).
 *
 * Extracted from ExportOptionsForm for RULE-04 file-size compliance.
 */

interface EpubOptionsGroupProps {
  readonly options: ExportOptions;
  /** Disable all inputs while an export is in flight. */
  readonly disabled: boolean;
  readonly onChange: (next: ExportOptions) => void;
}

export function EpubOptionsGroup({ options, disabled, onChange }: EpubOptionsGroupProps) {
  const t = useTranslations("export");

  return (
    <fieldset data-testid="epub-options">
      <legend className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
        {t("epub.label")}
      </legend>
      <label className="block py-1.5">
        <span className="block text-sm text-foreground mb-1">{t("epub.coverImage")}</span>
        <input
          type="text"
          value={options.epub_options?.cover_image_path ?? ""}
          disabled={disabled}
          onChange={(e) =>
            onChange({
              ...options,
              epub_options: {
                cover_image_path: e.target.value || null,
                css: options.epub_options?.css ?? null,
              },
            })
          }
          className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
      </label>
      <label className="block py-1.5">
        <span className="block text-sm text-foreground mb-1">{t("epub.css")}</span>
        <textarea
          value={options.epub_options?.css ?? ""}
          disabled={disabled}
          rows={3}
          onChange={(e) =>
            onChange({
              ...options,
              epub_options: {
                cover_image_path: options.epub_options?.cover_image_path ?? null,
                css: e.target.value || null,
              },
            })
          }
          className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
      </label>
    </fieldset>
  );
}
