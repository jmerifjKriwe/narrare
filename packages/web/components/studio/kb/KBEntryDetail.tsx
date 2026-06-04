"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { KBEntry, KBEntryStatus, KBRelationship } from "@/lib/api/kb";
import { useDeleteKBEntry, useKBTemplate, useUpdateKBEntry } from "@/lib/hooks/useKB";
import { TYPE_ICONS } from "./constants";
import { KBEntryAISections } from "./KBEntryAISections";
import { KBEntryHeader } from "./KBEntryHeader";
import { KBEntrySections } from "./KBEntrySections";
import { KBEntryTemplateFields } from "./KBEntryTemplateFields";
import { KBMetadataBar } from "./KBMetadataBar";
import { KBRelationshipSection } from "./KBRelationshipSection";
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
  const [confirmOpen, setConfirmOpen] = useState(false);
  const pendingAction = useRef<(() => void) | null>(null);

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
    pendingAction.current = () => deleteMutation.mutate(entry.id, { onSuccess: onDeleted });
    setConfirmOpen(true);
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

        <KBMetadataBar
          status={status}
          tags={tags}
          onStatusChange={setStatus}
          onTagsChange={setTags}
        />

        {updateMutation.isError && (
          <div
            className="px-4 py-3 rounded-lg bg-destructive/10 border border-destructive/20 text-sm text-destructive"
            role="alert"
          >
            {updateMutation.error?.message ?? "Failed to save"}
          </div>
        )}

        <KBEntryTemplateFields
          template={template}
          fieldValues={fieldValues}
          entryMetadata={entry.metadata}
          body={extraBody}
          onFieldChange={handleFieldChange}
          onBodyChange={setExtraBody}
          label={label}
          formatKey={formatKey}
        />

        <KBEntrySections
          novelId={novelId}
          sections={sortedSections}
          sectionContents={sectionContents}
          extraBody={extraBody}
          showExtraBody={hasTemplate}
          onSectionChange={(name, val) => setSectionContents((prev) => ({ ...prev, [name]: val }))}
          onExtraBodyChange={setExtraBody}
          label={label}
        />

        <div className="pt-2">
          <KBRelationshipSection novelId={novelId} entry={entry} relationships={relationships} />
        </div>

        <KBEntryAISections
          novelId={novelId}
          entryId={entry.id}
          entryName={entry.name}
          entityType={entry.entity_type}
        />
      </div>

      {/* Delete confirmation */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("kb.deleteEntry")}
        description={t("kb.deleteConfirm")}
        confirmLabel={t("kb.deleteEntry")}
        variant="destructive"
        onConfirm={() => {
          pendingAction.current?.();
          pendingAction.current = null;
          setConfirmOpen(false);
        }}
      />
    </div>
  );
}
