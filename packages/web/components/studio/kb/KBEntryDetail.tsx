"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import type { KBEntry, KBEntryStatus, KBRelationship } from "@/lib/api/kb";
import { useDeleteKBEntry, useKBTemplate, useUpdateKBEntry } from "@/lib/hooks/useKB";
import { TYPE_ICONS } from "./constants";
import { getGroupIcon, getSectionIcon } from "./groupMaps";
import { KBEntryHeader } from "./KBEntryHeader";
import { KBFieldGroup } from "./KBFieldGroup";
import { KBFlatEditor } from "./KBFlatEditor";
import { KBImprovePanel } from "./KBImprovePanel";
import { KBRelationshipSection } from "./KBRelationshipSection";
import { KBSectionEditor } from "./KBSectionEditor";
import { KBTagInput } from "./KBTagInput";
import { KBTypeField } from "./KBTypeField";
import { buildBodyFromSections, parseSectionsFromBody } from "./kbBodyUtils";

interface KBEntryDetailProps {
  novelId: string;
  entry: KBEntry;
  relationships: KBRelationship[];
  onDeleted: () => void;
}

function formatKey(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function KBEntryDetail({ novelId, entry, relationships, onDeleted }: KBEntryDetailProps) {
  const t = useTranslations("studio");
  const Icon = TYPE_ICONS[entry.entity_type];

  const { data: template, isLoading: templateLoading } = useKBTemplate(novelId, entry.entity_type);
  const hasTemplate = !!template && template.field_groups.length > 0;

  const updateMutation = useUpdateKBEntry(novelId);
  const deleteMutation = useDeleteKBEntry(novelId);

  const [name, setName] = useState(entry.name);
  const [status, setStatus] = useState<KBEntryStatus>(entry.status);
  const [tags, setTags] = useState<string[]>(entry.tags);
  const [fieldValues, setFieldValues] = useState<Record<string, unknown>>(entry.metadata);
  const [sectionContents, setSectionContents] = useState<Record<string, string>>({});
  const [extraBody, setExtraBody] = useState("");
  const [showImprovePanel, setShowImprovePanel] = useState(false);

  useEffect(() => {
    setName(entry.name);
    setStatus(entry.status);
    setTags(entry.tags);
    setFieldValues(entry.metadata as Record<string, unknown>);
    if (template?.sections?.length) {
      const { sectionContents: parsed, remaining } = parseSectionsFromBody(
        entry.body,
        template.sections,
      );
      setSectionContents(parsed);
      setExtraBody(remaining);
    } else setExtraBody(entry.body);
  }, [entry, template]);

  const sortedGroups = useMemo(
    () => [...(template?.field_groups ?? [])].sort((a, b) => a.order - b.order),
    [template],
  );
  const sortedSections = useMemo(
    () => [...(template?.sections ?? [])].sort((a, b) => a.order - b.order),
    [template],
  );

  const label = (key: string, fb: string) => {
    const v = t(key);
    return v !== key ? v : fb;
  };

  function handleSave() {
    const body = hasTemplate
      ? buildBodyFromSections(template!.sections, sectionContents, extraBody)
      : extraBody;
    updateMutation.mutate({
      entryId: entry.id,
      data: { name, body, tags, status, metadata: fieldValues },
    });
  }

  function handleDelete() {
    if (!window.confirm(t("kb.deleteConfirm"))) return;
    deleteMutation.mutate(entry.id, { onSuccess: onDeleted });
  }

  const handleFieldChange = (fieldName: string, value: unknown) =>
    setFieldValues((prev) => ({ ...prev, [fieldName]: value }));

  if (templateLoading) {
    return (
      <div className="flex-1 overflow-y-auto bg-background flex items-center justify-center min-h-[40vh]">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const statusOptions: KBEntryStatus[] = ["draft", "reviewed", "canon", "deprecated"];

  return (
    <div className="flex-1 overflow-y-auto bg-background">
      <div className="max-w-3xl mx-auto p-8 space-y-6">
        <KBEntryHeader
          name={name}
          status={status}
          statusLabel={t(`kb.status.${status}`)}
          Icon={Icon}
          namePlaceholder={t("kb.namePlaceholder")}
          isSaving={updateMutation.isPending}
          isDeleting={deleteMutation.isPending}
          onNameChange={setName}
          onSave={handleSave}
          onDelete={handleDelete}
          deleteLabel={t("kb.deleteEntry")}
          saveLabel={t("kb.save")}
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="entry-status"
              className="block text-xs font-medium text-muted-foreground mb-1.5"
            >
              {t("metadataSidebar.status")}
            </label>
            <select
              id="entry-status"
              value={status}
              onChange={(e) => setStatus(e.target.value as KBEntryStatus)}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm
                transition-colors duration-150 hover:border-muted-foreground/30
                focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/20"
            >
              {statusOptions.map((s) => (
                <option key={s} value={s}>
                  {t(`kb.status.${s}`)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <span className="block text-xs font-medium text-muted-foreground mb-1.5">
              {t("kb.tags")}
            </span>
            <KBTagInput value={tags} onChange={setTags} placeholder={t("kb.tagsPlaceholder")} />
          </div>
        </div>
        {updateMutation.isError && (
          <div
            className="px-4 py-3 rounded-lg bg-destructive/10 border border-destructive/20 text-sm text-destructive"
            role="alert"
          >
            {updateMutation.error?.message ?? "Failed to save"}
          </div>
        )}

        {hasTemplate ? (
          <div className="space-y-3">
            {sortedGroups.map((group) => {
              const iconMeta = getGroupIcon(group.name);
              return (
                <KBFieldGroup
                  key={group.name}
                  icon={iconMeta.icon}
                  iconColor={iconMeta.color}
                  title={label(`kb.groups.${group.name}`, formatKey(group.name))}
                  description={group.description_key ? t(group.description_key) : undefined}
                >
                  {group.fields.map((field) => (
                    <KBTypeField
                      key={field.name}
                      field={field}
                      value={fieldValues[field.name]}
                      onChange={handleFieldChange}
                      label={label(
                        `kb.groupLabels.${group.name}.${field.name}`,
                        formatKey(field.name),
                      )}
                      groupName={group.name}
                    />
                  ))}
                </KBFieldGroup>
              );
            })}
          </div>
        ) : (
          <KBFlatEditor
            template={template}
            fieldValues={fieldValues}
            body={extraBody}
            entryMetadata={entry.metadata}
            onFieldChange={handleFieldChange}
            onBodyChange={setExtraBody}
          />
        )}

        {sortedSections.length > 0 && (
          <div className="space-y-4">
            <div className="h-px bg-border/50" />
            {sortedSections.map((section) => {
              const iconMeta = getSectionIcon(section.name);
              return (
                <KBSectionEditor
                  key={section.name}
                  name={section.name}
                  novelId={novelId}
                  icon={iconMeta.icon}
                  iconColor={iconMeta.color}
                  title={label(`kb.sections.${section.name}`, formatKey(section.name))}
                  hint={label(`kb.sections.${section.name}Hint`, "")}
                  value={sectionContents[section.name] ?? ""}
                  onChange={(name, val) => setSectionContents((prev) => ({ ...prev, [name]: val }))}
                />
              );
            })}
          </div>
        )}

        {hasTemplate && extraBody.trim() && (
          <div>
            <label
              htmlFor="entry-extra-body"
              className="block text-xs font-medium text-muted-foreground mb-1.5"
            >
              {t("kb.additionalNotes")}
            </label>
            <textarea
              id="entry-extra-body"
              value={extraBody}
              onChange={(e) => setExtraBody(e.target.value)}
              rows={4}
              className="w-full px-3 py-2 bg-input-background border border-border/60 rounded-md text-sm resize-y
                transition-colors duration-150 hover:border-muted-foreground/30
                focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/10"
            />
          </div>
        )}

        <div className="pt-2">
          <KBRelationshipSection novelId={novelId} entry={entry} relationships={relationships} />
        </div>

        {/* AI Improve section */}
        <div className="pt-4 border-t border-border/50">
          {showImprovePanel ? (
            <KBImprovePanel
              novelId={novelId}
              entryId={entry.id}
              onClose={() => setShowImprovePanel(false)}
              onApplied={() => setShowImprovePanel(false)}
            />
          ) : (
            <button
              type="button"
              onClick={() => setShowImprovePanel(true)}
              className="flex items-center gap-2 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
            >
              <Sparkles className="w-4 h-4 text-purple-500" />
              {t("kb.improveWithAI")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
