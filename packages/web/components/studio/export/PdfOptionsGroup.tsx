"use client";

import { useTranslations } from "next-intl";
import type { ExportOptions, PaperSize, PdfOptions } from "@/types";
import { NumberField, ToggleRow } from "./ExportFormFields";

/**
 * PdfOptionsGroup — the PDF-only options fieldset (paper size, typography,
 * drop caps, TOC).
 *
 * Extracted from ExportOptionsForm for RULE-04 file-size compliance.
 */

const PAPER_SIZES: PaperSize[] = ["b-format-129x198", "a5", "a4", "letter", "custom"];
const PAPER_KEYS: Record<PaperSize, string> = {
  "b-format-129x198": "pdf.paperBFormat",
  a5: "pdf.paperA5",
  a4: "pdf.paperA4",
  letter: "pdf.paperLetter",
  custom: "pdf.paperCustom",
};

/** Fallback when pdf_options is null — mirrors NarrareRomanConfig defaults. */
const DEFAULT_PDF_OPTIONS: PdfOptions = {
  paper_size: "b-format-129x198",
  margins: null,
  body_size_pt: 11,
  leading_ratio: 1.2,
  drop_caps: false,
  include_toc: true,
};

interface PdfOptionsGroupProps {
  readonly options: ExportOptions;
  /** Disable all inputs while an export is in flight. */
  readonly disabled: boolean;
  readonly onChange: (next: ExportOptions) => void;
}

export function PdfOptionsGroup({ options, disabled, onChange }: PdfOptionsGroupProps) {
  const t = useTranslations("export");
  const pdf = options.pdf_options ?? DEFAULT_PDF_OPTIONS;

  return (
    <fieldset data-testid="pdf-options">
      <legend className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
        {t("pdf.label")}
      </legend>
      <label className="flex items-center justify-between py-1.5">
        <span className="text-sm text-foreground">{t("pdf.paperSize")}</span>
        <select
          value={pdf.paper_size}
          disabled={disabled}
          onChange={(e) =>
            onChange({
              ...options,
              pdf_options: { ...pdf, paper_size: e.target.value as PaperSize },
            })
          }
          className="w-40 rounded-md border border-border bg-background px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          {PAPER_SIZES.map((size) => (
            <option key={size} value={size}>
              {t(PAPER_KEYS[size])}
            </option>
          ))}
        </select>
      </label>
      <NumberField
        label={t("pdf.fontSize")}
        value={pdf.body_size_pt}
        min={6}
        max={48}
        step={0.5}
        disabled={disabled}
        onChange={(v) => onChange({ ...options, pdf_options: { ...pdf, body_size_pt: v } })}
      />
      <NumberField
        label={t("pdf.leading")}
        value={pdf.leading_ratio}
        min={0.8}
        max={3}
        step={0.05}
        disabled={disabled}
        onChange={(v) => onChange({ ...options, pdf_options: { ...pdf, leading_ratio: v } })}
      />
      <ToggleRow
        label={t("pdf.dropCaps")}
        checked={pdf.drop_caps}
        disabled={disabled}
        onCheckedChange={(v) => onChange({ ...options, pdf_options: { ...pdf, drop_caps: v } })}
      />
      <ToggleRow
        label={t("pdf.tableOfContents")}
        checked={pdf.include_toc}
        disabled={disabled}
        onCheckedChange={(v) => onChange({ ...options, pdf_options: { ...pdf, include_toc: v } })}
      />
    </fieldset>
  );
}
