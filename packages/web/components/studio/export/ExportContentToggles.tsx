"use client";

import { useTranslations } from "next-intl";
import type { ExportOptions } from "@/types";
import { ToggleRow } from "./ExportFormFields";

/**
 * ExportContentToggles — the common content-inclusion switches of the
 * export form (front/back matter, summaries, character list, glossary).
 *
 * Extracted from ExportOptionsForm for RULE-04 file-size compliance.
 */

interface ExportContentTogglesProps {
  readonly options: ExportOptions;
  /** Disable all inputs while an export is in flight. */
  readonly disabled: boolean;
  readonly onChange: (next: ExportOptions) => void;
}

export function ExportContentToggles({ options, disabled, onChange }: ExportContentTogglesProps) {
  const t = useTranslations("export");

  return (
    <fieldset>
      <legend className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
        {t("content.label")}
      </legend>
      <ToggleRow
        label={t("content.frontMatter")}
        checked={options.include_front_matter}
        disabled={disabled}
        onCheckedChange={(v) => onChange({ ...options, include_front_matter: v })}
      />
      <ToggleRow
        label={t("content.backMatter")}
        checked={options.include_back_matter}
        disabled={disabled}
        onCheckedChange={(v) => onChange({ ...options, include_back_matter: v })}
      />
      <ToggleRow
        label={t("content.summaries")}
        checked={options.include_summaries}
        disabled={disabled}
        onCheckedChange={(v) => onChange({ ...options, include_summaries: v })}
      />
      <ToggleRow
        label={t("content.characterList")}
        checked={options.include_character_list}
        disabled={disabled}
        onCheckedChange={(v) => onChange({ ...options, include_character_list: v })}
      />
      <ToggleRow
        label={t("content.locationGlossary")}
        checked={options.include_location_glossary}
        disabled={disabled}
        onCheckedChange={(v) => onChange({ ...options, include_location_glossary: v })}
      />
    </fieldset>
  );
}
