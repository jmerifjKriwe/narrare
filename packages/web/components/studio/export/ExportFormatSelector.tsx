"use client";

import type { LucideIcon } from "lucide-react";
import { BookOpen, FileText, FileType2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ExportFormat, ExportOptions } from "@/types";

/**
 * ExportFormatSelector — the output-format card group of the export form.
 *
 * Extracted from ExportOptionsForm for RULE-04 file-size compliance.
 * Unavailable formats are disabled and labelled; selecting a card writes
 * the new format into the shared options object.
 */

const FORMAT_CARDS: { value: ExportFormat; icon: LucideIcon; labelKey: string; descKey: string }[] =
  [
    { value: "pdf", icon: FileText, labelKey: "format.pdf", descKey: "format.pdfDescription" },
    { value: "epub", icon: BookOpen, labelKey: "format.epub", descKey: "format.epubDescription" },
    {
      value: "md",
      icon: FileType2,
      labelKey: "format.markdown",
      descKey: "format.markdownDescription",
    },
  ];

interface ExportFormatSelectorProps {
  readonly options: ExportOptions;
  readonly isFormatAvailable: (format: ExportFormat) => boolean;
  readonly disabled: boolean;
  readonly onChange: (next: ExportOptions) => void;
}

export function ExportFormatSelector({
  options,
  isFormatAvailable,
  disabled,
  onChange,
}: ExportFormatSelectorProps) {
  const t = useTranslations("export");

  return (
    <fieldset>
      <legend className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
        {t("format.label")}
      </legend>
      <div className="grid grid-cols-1 gap-2">
        {FORMAT_CARDS.map(({ value, icon: Icon, labelKey, descKey }) => {
          const available = isFormatAvailable(value);
          const selected = options.format === value;
          return (
            <button
              key={value}
              type="button"
              disabled={disabled || !available}
              onClick={() => onChange({ ...options, format: value })}
              aria-pressed={selected}
              className={cnFormatCard(selected, available)}
              data-testid={`format-${value}`}
            >
              <Icon className="w-5 h-5 shrink-0" aria-hidden="true" />
              <span className="flex-1 text-left">
                <span className="block text-sm font-medium text-foreground">{t(labelKey)}</span>
                <span className="block text-xs text-muted-foreground">{t(descKey)}</span>
              </span>
              {!available && (
                <span className="text-xs text-muted-foreground">{t("format.unavailable")}</span>
              )}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

/** Tailwind classes for a format card (selected / available combos). */
function cnFormatCard(selected: boolean, available: boolean): string {
  const base = "flex items-center gap-3 rounded-lg border p-3 text-left transition-colors";
  if (!available) return `${base} border-border bg-muted/40 opacity-60 cursor-not-allowed`;
  if (selected) return `${base} border-primary bg-accent ring-1 ring-primary`;
  return `${base} border-border hover:bg-accent`;
}
