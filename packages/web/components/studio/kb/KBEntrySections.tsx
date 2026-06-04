"use client";

/**
 * KBEntrySections — Template-driven sections and extra body editor for KB entry detail.
 *
 * Extracted from KBEntryDetail for RULE-04 compliance.
 */

import type { KBTemplateSection } from "@/lib/api/kb";
import { getSectionIcon } from "./groupMaps";
import { KBSectionEditor } from "./KBSectionEditor";

interface KBEntrySectionsProps {
  novelId: string;
  sections: KBTemplateSection[];
  sectionContents: Record<string, string>;
  extraBody: string;
  showExtraBody: boolean;
  onSectionChange: (name: string, value: string) => void;
  onExtraBodyChange: (value: string) => void;
  label: (key: string, fallback: string) => string;
}

export function KBEntrySections({
  novelId,
  sections,
  sectionContents,
  extraBody,
  showExtraBody,
  onSectionChange,
  onExtraBodyChange,
  label,
}: KBEntrySectionsProps) {
  if (sections.length === 0 && !showExtraBody) return null;

  return (
    <>
      {sections.length > 0 && (
        <div className="space-y-4">
          <div className="h-px bg-border/50" />
          {sections.map((section) => {
            const iconMeta = getSectionIcon(section.name);
            return (
              <KBSectionEditor
                key={section.name}
                name={section.name}
                novelId={novelId}
                icon={iconMeta.icon}
                iconColor={iconMeta.color}
                title={label(`kb.sections.${section.name}`, section.name)}
                hint={label(`kb.sections.${section.name}Hint`, "")}
                value={sectionContents[section.name] ?? ""}
                onChange={onSectionChange}
              />
            );
          })}
        </div>
      )}

      {showExtraBody && extraBody.trim() && (
        <div>
          <label
            htmlFor="entry-extra-body"
            className="block text-xs font-medium text-muted-foreground mb-1.5"
          >
            {label("kb.additionalNotes", "Additional Notes")}
          </label>
          <textarea
            id="entry-extra-body"
            value={extraBody}
            onChange={(e) => onExtraBodyChange(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 bg-input-background border border-border/60 rounded-md text-sm resize-y
              transition-colors duration-150 hover:border-muted-foreground/30
              focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/10"
          />
        </div>
      )}
    </>
  );
}
