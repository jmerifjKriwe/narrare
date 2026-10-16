"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { ScopeToggle } from "@/components/kb/ScopeToggle";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { KBEntry, KBEntryStatus, KBRelationship } from "@/lib/api/kb";
import { useDeleteKBEntry, useKBTemplate, useUpdateKBEntry } from "@/lib/hooks/useKB";
import { TYPE_ICONS } from "./constants";
import { KBEntryAISections } from "./KBEntryAISections";
import { KBEntryHeader } from "./KBEntryHeader";
import { KBFlatEditor } from "./KBFlatEditor";
import { KBMetadataBar } from "./KBMetadataBar";
import { KBRelationshipSection } from "./KBRelationshipSection";

interface KBEntryDetailProps {
  novelId: string;
  entry: KBEntry;
  relationships: KBRelationship[];
  onDeleted: () => void;
}

export function KBEntryDetail({ novelId, entry, relationships, onDeleted }: KBEntryDetailProps) {
  const t = useTranslations("studio");
  const Icon = TYPE_ICONS[entry.entity_type];

  const { isLoading: templateLoading } = useKBTemplate(novelId, entry.entity_type);

  const updateMutation = useUpdateKBEntry(novelId);
  const deleteMutation = useDeleteKBEntry(novelId);

  const [name, setName] = useState(entry.name);
  const [status, setStatus] = useState<KBEntryStatus>(entry.status);
  const [tags, setTags] = useState<string[]>(entry.tags);
  // Legacy rows can carry the JSON scalar null in the metadata column
  // (pre-fix creates persisted Python None as jsonb null); the write path
  // now coerces to {}, and the read side defaults here so the flat
  // editor's Object.keys never sees null (B04-class crash guard).
  const metadata = entry.metadata ?? {};
  const [fieldValues, setFieldValues] = useState<Record<string, unknown>>(metadata);
  const [extraBody, setExtraBody] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const pendingAction = useRef<(() => void) | null>(null);

  useEffect(() => {
    setName(entry.name);
    setStatus(entry.status);
    setTags(entry.tags);
    setFieldValues(entry.metadata ?? {});
    setExtraBody(entry.body);
  }, [entry]);

  function handleSave() {
    const body = extraBody;
    updateMutation.mutate({
      entryId: entry.id,
      data: { name, body, tags, status, metadata: fieldValues },
    });
  }

  function handleDelete() {
    pendingAction.current = () => deleteMutation.mutate(entry.id, { onSuccess: onDeleted });
    setConfirmOpen(true);
  }

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

        {/*
         * Scope toggle — Series-Canon vs Novel-Overlay. Renders nothing when the
         * novel is standalone (useNovelSeries → null inside the component), so it
         * is a no-op for non-series novels. Novel-editor entries are always
         * Novel-Overlays (Canon entries live under /series/{id}/kb).
         */}
        <ScopeToggle entry={{ id: entry.id, scope: "novel" }} novelId={novelId} />

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
            {t("kb.failedToSaveEntry")}
          </div>
        )}

        <KBFlatEditor entryMetadata={metadata} body={extraBody} onBodyChange={setExtraBody} />

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
