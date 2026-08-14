"use client";

import type { ExportFormat, ExportOptions } from "@/types";
import { EpubOptionsGroup } from "./EpubOptionsGroup";
import { ExportContentToggles } from "./ExportContentToggles";
import { ExportFormatSelector } from "./ExportFormatSelector";
import { MarkdownOptionsGroup } from "./MarkdownOptionsGroup";
import { PdfOptionsGroup } from "./PdfOptionsGroup";

/**
 * ExportOptionsForm — composition shell of the export options form.
 *
 * RULE-06: purely composes the focused field groups (format selector,
 * content toggles, per-format option groups); each group owns its own
 * i18n labels and updates the shared options object immutably.
 */

interface ExportOptionsFormProps {
  readonly options: ExportOptions;
  readonly isFormatAvailable: (format: ExportFormat) => boolean;
  /** Disable all inputs while an export is in flight. */
  readonly disabled: boolean;
  readonly onChange: (next: ExportOptions) => void;
}

export function ExportOptionsForm({
  options,
  isFormatAvailable,
  disabled,
  onChange,
}: ExportOptionsFormProps) {
  return (
    <div className="space-y-6">
      {/* Format selector */}
      <ExportFormatSelector
        options={options}
        isFormatAvailable={isFormatAvailable}
        disabled={disabled}
        onChange={onChange}
      />

      {/* Common content inclusions */}
      <ExportContentToggles options={options} disabled={disabled} onChange={onChange} />

      {/* Format-specific options */}
      {options.format === "pdf" && (
        <PdfOptionsGroup options={options} disabled={disabled} onChange={onChange} />
      )}

      {options.format === "epub" && (
        <EpubOptionsGroup options={options} disabled={disabled} onChange={onChange} />
      )}

      {options.format === "md" && (
        <MarkdownOptionsGroup options={options} disabled={disabled} onChange={onChange} />
      )}
    </div>
  );
}
