"use client";

/**
 * KBEntryTemplateFields — Template-driven field groups for KB entry detail.
 *
 * Extracted from KBEntryDetail for RULE-04 compliance.
 */

import type { KBTemplate } from "@/lib/api/kb";
import { getGroupIcon } from "./groupMaps";
import { KBFieldGroup } from "./KBFieldGroup";
import { KBFlatEditor } from "./KBFlatEditor";
import { KBTypeField } from "./KBTypeField";

interface KBEntryTemplateFieldsProps {
  template: KBTemplate | null | undefined;
  fieldValues: Record<string, unknown>;
  entryMetadata: Record<string, unknown>;
  body: string;
  onFieldChange: (fieldName: string, value: unknown) => void;
  onBodyChange: (value: string) => void;
  label: (key: string, fallback: string) => string;
  formatKey: (key: string) => string;
}

export function KBEntryTemplateFields({
  template,
  fieldValues,
  entryMetadata,
  body,
  onFieldChange,
  onBodyChange,
  label,
  formatKey,
}: KBEntryTemplateFieldsProps) {
  const hasTemplate = !!template && template.field_groups.length > 0;

  if (!hasTemplate) {
    return (
      <KBFlatEditor
        template={template}
        fieldValues={fieldValues}
        body={body}
        entryMetadata={entryMetadata}
        onFieldChange={onFieldChange}
        onBodyChange={onBodyChange}
      />
    );
  }

  const sortedGroups = [...template.field_groups].sort((a, b) => a.order - b.order);

  return (
    <div className="space-y-3">
      {sortedGroups.map((group) => {
        const iconMeta = getGroupIcon(group.name);
        return (
          <KBFieldGroup
            key={group.name}
            icon={iconMeta.icon}
            iconColor={iconMeta.color}
            title={label(`kb.groups.${group.name}`, formatKey(group.name))}
            description={group.description_key ? label(group.description_key, "") : undefined}
          >
            {group.fields.map((field) => (
              <KBTypeField
                key={field.name}
                field={field}
                value={fieldValues[field.name]}
                onChange={onFieldChange}
                label={label(`kb.groupLabels.${group.name}.${field.name}`, formatKey(field.name))}
                groupName={group.name}
              />
            ))}
          </KBFieldGroup>
        );
      })}
    </div>
  );
}
