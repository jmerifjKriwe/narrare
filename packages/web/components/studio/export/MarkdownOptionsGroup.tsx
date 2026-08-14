"use client";

import { useTranslations } from "next-intl";
import type { ExportOptions, MarkdownOptions } from "@/types";
import { NumberField } from "./ExportFormFields";

/**
 * MarkdownOptionsGroup — the Markdown-only options fieldset (chapter
 * heading level).
 *
 * Extracted from ExportOptionsForm for RULE-04 file-size compliance.
 */

/** Fallback when markdown_options is null — mirrors the pandoc defaults. */
const DEFAULT_MARKDOWN_OPTIONS: MarkdownOptions = {
  chapter_heading_level: 1,
  include_front_matter: true,
};

interface MarkdownOptionsGroupProps {
  readonly options: ExportOptions;
  /** Disable all inputs while an export is in flight. */
  readonly disabled: boolean;
  readonly onChange: (next: ExportOptions) => void;
}

export function MarkdownOptionsGroup({ options, disabled, onChange }: MarkdownOptionsGroupProps) {
  const t = useTranslations("export");
  const md = options.markdown_options ?? DEFAULT_MARKDOWN_OPTIONS;

  return (
    <fieldset data-testid="markdown-options">
      <legend className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
        {t("markdown.label")}
      </legend>
      <NumberField
        label={t("markdown.chapterHeadingLevel")}
        value={md.chapter_heading_level}
        min={1}
        max={6}
        step={1}
        disabled={disabled}
        onChange={(v) =>
          onChange({ ...options, markdown_options: { ...md, chapter_heading_level: v } })
        }
      />
    </fieldset>
  );
}
