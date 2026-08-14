"use client";

import { useTranslations } from "next-intl";
import type { EpubOptions, ExportOptions } from "@/types";

/**
 * EpubOptionsGroup — the EPUB-only options fieldset (cover image path, ISBN,
 * custom CSS, description).
 *
 * Extracted from ExportOptionsForm for RULE-04 file-size compliance.
 * `isbn` / `description` are optional EPUB metadata (IO-001 follow-up):
 * leave-empty = unset (null) — no validation, mirroring cover/CSS.
 */

/** Fallback when epub_options is null — all metadata unset. */
const DEFAULT_EPUB_OPTIONS: EpubOptions = {
  cover_image_path: null,
  css: null,
  isbn: null,
  description: null,
};

interface EpubOptionsGroupProps {
  readonly options: ExportOptions;
  /** Disable all inputs while an export is in flight. */
  readonly disabled: boolean;
  readonly onChange: (next: ExportOptions) => void;
}

export function EpubOptionsGroup({ options, disabled, onChange }: EpubOptionsGroupProps) {
  const t = useTranslations("export");
  const epub = options.epub_options ?? DEFAULT_EPUB_OPTIONS;

  return (
    <fieldset data-testid="epub-options">
      <legend className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
        {t("epub.label")}
      </legend>
      <label className="block py-1.5">
        <span className="block text-sm text-foreground mb-1">{t("epub.coverImage")}</span>
        <input
          type="text"
          value={epub.cover_image_path ?? ""}
          disabled={disabled}
          onChange={(e) =>
            onChange({
              ...options,
              epub_options: { ...epub, cover_image_path: e.target.value || null },
            })
          }
          className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
      </label>
      <label className="block py-1.5">
        <span className="block text-sm text-foreground mb-1">{t("epub.isbn")}</span>
        <input
          type="text"
          placeholder={t("epub.isbnPlaceholder")}
          value={epub.isbn ?? ""}
          disabled={disabled}
          onChange={(e) =>
            onChange({
              ...options,
              epub_options: { ...epub, isbn: e.target.value || null },
            })
          }
          className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
      </label>
      <label className="block py-1.5">
        <span className="block text-sm text-foreground mb-1">{t("epub.css")}</span>
        <textarea
          value={epub.css ?? ""}
          disabled={disabled}
          rows={3}
          onChange={(e) =>
            onChange({
              ...options,
              epub_options: { ...epub, css: e.target.value || null },
            })
          }
          className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
      </label>
      <label className="block py-1.5">
        <span className="block text-sm text-foreground mb-1">{t("epub.description")}</span>
        <textarea
          rows={3}
          placeholder={t("epub.descriptionPlaceholder")}
          value={epub.description ?? ""}
          disabled={disabled}
          onChange={(e) =>
            onChange({
              ...options,
              epub_options: { ...epub, description: e.target.value || null },
            })
          }
          className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
      </label>
    </fieldset>
  );
}
