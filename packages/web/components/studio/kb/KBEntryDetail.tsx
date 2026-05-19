"use client";

/**
 * KB Entry Detail — shows and edits a single KB entry.
 *
 * Displays: name (inline editable), entity type icon, status selector,
 * tags, body textarea, metadata, and relationship section.
 */

import { Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import type { KBEntry, KBEntryStatus, KBRelationship } from "@/lib/api/kb";
import { useDeleteKBEntry, useUpdateKBEntry } from "@/lib/hooks/useKB";
import { TYPE_ICONS } from "./constants";
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

  const updateMutation = useUpdateKBEntry(novelId);
  const deleteMutation = useDeleteKBEntry(novelId);

  const [name, setName] = useState(entry.name);
  const [body, setBody] = useState(entry.body);
  const [tagsInput, setTagsInput] = useState(entry.tags.join(", "));
  const [status, setStatus] = useState<KBEntryStatus>(entry.status);

  useEffect(() => {
    setName(entry.name);
    setBody(entry.body);
    setTagsInput(entry.tags.join(", "));
    setStatus(entry.status);
  }, [entry.name, entry.body, entry.tags, entry.status]);

  function handleSave() {
    const tags = tagsInput
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    updateMutation.mutate({ entryId: entry.id, data: { name, body, tags, status } });
  }

  function handleDelete() {
    if (!window.confirm(t("kb.deleteConfirm"))) return;
    deleteMutation.mutate(entry.id, { onSuccess: onDeleted });
  }

  return (
    <div className="flex-1 overflow-y-auto bg-background">
      <div className="max-w-3xl mx-auto p-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-xl bg-muted flex items-center justify-center">
              <Icon className="w-6 h-6 text-muted-foreground" />
            </div>
            <div>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="text-2xl font-medium bg-transparent border-none outline-none w-full"
              />
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  {t(`kb.status.${status}`)}
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={updateMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm text-sm disabled:opacity-50"
            >
              {t("kb.save")}
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              className="p-2 text-destructive hover:bg-destructive/10 rounded-md disabled:opacity-50"
              aria-label={t("kb.deleteEntry")}
            >
              <Trash2 className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="space-y-6">
          {/* Status selector */}
          <FieldGroup label={t("metadataSidebar.status")} htmlFor="entry-status">
            <select
              id="entry-status"
              value={status}
              onChange={(e) => setStatus(e.target.value as KBEntryStatus)}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm"
            >
              {(["draft", "reviewed", "canon", "deprecated"] as KBEntryStatus[]).map((s) => (
                <option key={s} value={s}>
                  {t(`kb.status.${s}`)}
                </option>
              ))}
            </select>
          </FieldGroup>

          {/* Tags */}
          <FieldGroup label={t("kb.tags")} htmlFor="entry-tags">
            <input
              id="entry-tags"
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder={t("kb.tagsPlaceholder")}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm"
            />
          </FieldGroup>

          {/* Body */}
          <FieldGroup label={t("kb.body")} htmlFor="entry-body">
            <textarea
              id="entry-body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={t("kb.bodyPlaceholder")}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm min-h-[200px] resize-y"
            />
          </FieldGroup>

          {/* Metadata */}
          {Object.keys(entry.metadata).length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-1.5">
                {t("kb.metadata")}
              </h3>
              <div className="bg-muted/30 rounded-md p-3 space-y-1">
                {Object.entries(entry.metadata).map(([key, value]) => (
                  <div key={key} className="flex items-center gap-2 text-sm">
                    <span className="text-muted-foreground font-medium">{key}:</span>
                    <span>{String(value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Relationships */}
          <KBRelationshipSection novelId={novelId} entry={entry} relationships={relationships} />
        </div>
      </div>
    </div>
  );
}

// --- Reusable field group ---

interface FieldGroupProps {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}

function FieldGroup({ label, htmlFor, children }: FieldGroupProps) {
  return (
    <div>
      <label htmlFor={htmlFor} className="block text-sm font-medium text-muted-foreground mb-1.5">
        {label}
      </label>
      {children}
    </div>
  );
}
