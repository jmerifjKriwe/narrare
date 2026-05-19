"use client";

/**
 * Fallback flat editor for KB entries without a template.
 *
 * Renders:
 * - A flat list of template fields (if available) as typed inputs
 * - A metadata key-value read-only display (if no template fields)
 * - A single body textarea for free-form content
 */

import { useTranslations } from "next-intl";
import type { KBTemplate } from "@/lib/api/kb";
import { KBTypeField } from "./KBTypeField";

interface KBFlatEditorProps {
  template: KBTemplate | null | undefined;
  fieldValues: Record<string, unknown>;
  body: string;
  entryMetadata: Record<string, unknown>;
  onFieldChange: (name: string, value: unknown) => void;
  onBodyChange: (body: string) => void;
}

/** Format a snake_case identifier as a human-readable label. */
function formatKey(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function KBFlatEditor({
  template,
  fieldValues,
  body,
  entryMetadata,
  onFieldChange,
  onBodyChange,
}: KBFlatEditorProps) {
  const t = useTranslations("studio");
  const hasFlatFields = template?.fields && template.fields.length > 0;

  return (
    <div className="space-y-4">
      {hasFlatFields ? (
        <div className="space-y-3 p-4 border border-border/60 rounded-lg bg-card">
          <h3 className="text-sm font-semibold text-foreground">{t("kb.metadata")}</h3>
          {template!.fields.map((field) => (
            <KBTypeField
              key={field.name}
              field={field}
              value={fieldValues[field.name]}
              onChange={onFieldChange}
              label={formatKey(field.name)}
            />
          ))}
        </div>
      ) : Object.keys(entryMetadata).length > 0 ? (
        <div>
          <span className="block text-sm font-medium text-muted-foreground mb-1.5">
            {t("kb.metadata")}
          </span>
          <div className="bg-muted/30 rounded-md p-3 space-y-1">
            {Object.entries(entryMetadata).map(([key, val]) => (
              <div key={key} className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground font-medium">{formatKey(key)}:</span>
                <span>{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Flat body textarea */}
      <div>
        <label
          htmlFor="entry-body"
          className="block text-sm font-medium text-muted-foreground mb-1.5"
        >
          {t("kb.body")}
        </label>
        <textarea
          id="entry-body"
          value={body}
          onChange={(e) => onBodyChange(e.target.value)}
          placeholder={t("kb.bodyPlaceholder")}
          rows={8}
          className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm
            min-h-[200px] resize-y transition-colors duration-150
            hover:border-muted-foreground/30 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/20"
        />
      </div>
    </div>
  );
}
