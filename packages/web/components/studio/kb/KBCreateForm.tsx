"use client";

/**
 * KB Create Form — form for creating a new KB entry.
 *
 * Fields: entity type selector, name, body, tags, status.
 */

import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { KBEntityType, KBEntryStatus } from "@/lib/api/kb";
import { useCreateKBEntry } from "@/lib/hooks/useKB";
import { ENTITY_TYPES } from "./constants";

interface KBCreateFormProps {
  novelId: string;
  initialEntityType?: KBEntityType;
  onCancel: () => void;
  onCreated: (entryId: string) => void;
}

export function KBCreateForm({
  novelId,
  initialEntityType,
  onCancel,
  onCreated,
}: KBCreateFormProps) {
  const t = useTranslations("studio");

  const [entityType, setEntityType] = useState<KBEntityType>(initialEntityType ?? "character");
  const [name, setName] = useState("");
  const [body, setBody] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [status, setStatus] = useState<KBEntryStatus>("draft");

  const createMutation = useCreateKBEntry(novelId);

  function handleCreate() {
    if (!name.trim()) return;
    const tags = tagsInput
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    createMutation.mutate(
      { entity_type: entityType, name: name.trim(), body, tags, status },
      { onSuccess: (newEntry) => onCreated(newEntry.id) },
    );
  }

  /** Map entity type to its i18n key. */
  function typeLabel(type: KBEntityType): string {
    const map: Record<KBEntityType, string> = {
      character: "kb.characters",
      concept: "kb.concepts",
      location: "kb.locations",
      faction: "kb.factions",
      object: "kb.objects",
      setting: "kb.settings",
      system: "kb.systems",
      timeline: "kb.timelines",
    };
    return t(map[type]);
  }

  return (
    <div className="flex-1 overflow-y-auto bg-background">
      <div className="max-w-3xl mx-auto p-8">
        <div className="flex items-center gap-4 mb-8">
          <div className="w-14 h-14 rounded-xl bg-muted flex items-center justify-center">
            <Plus className="w-6 h-6 text-muted-foreground" />
          </div>
          <div>
            <h2 className="text-xl font-medium">{t("kb.newEntry")}</h2>
          </div>
        </div>

        <div className="space-y-4">
          {/* Entity type */}
          <div>
            <label
              htmlFor="create-type"
              className="block text-sm font-medium text-muted-foreground mb-1.5"
            >
              {t("kb.selectType")}
            </label>
            <select
              id="create-type"
              value={entityType}
              onChange={(e) => setEntityType(e.target.value as KBEntityType)}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm"
            >
              {ENTITY_TYPES.map((type) => (
                <option key={type} value={type}>
                  {typeLabel(type)}
                </option>
              ))}
            </select>
          </div>

          {/* Name */}
          <div>
            <label
              htmlFor="create-name"
              className="block text-sm font-medium text-muted-foreground mb-1.5"
            >
              {t("worldbuilding.name")}
            </label>
            <input
              id="create-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("kb.namePlaceholder")}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm"
            />
          </div>

          {/* Body */}
          <div>
            <label
              htmlFor="create-body"
              className="block text-sm font-medium text-muted-foreground mb-1.5"
            >
              {t("kb.body")}
            </label>
            <textarea
              id="create-body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={t("kb.bodyPlaceholder")}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm min-h-[150px] resize-y"
            />
          </div>

          {/* Tags */}
          <div>
            <label
              htmlFor="create-tags"
              className="block text-sm font-medium text-muted-foreground mb-1.5"
            >
              {t("kb.tags")}
            </label>
            <input
              id="create-tags"
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder={t("kb.tagsPlaceholder")}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm"
            />
          </div>

          {/* Status */}
          <div>
            <label
              htmlFor="create-status"
              className="block text-sm font-medium text-muted-foreground mb-1.5"
            >
              {t("metadataSidebar.status")}
            </label>
            <select
              id="create-status"
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
          </div>

          {/* Buttons */}
          <div className="flex items-center gap-3 pt-4">
            <button
              type="button"
              onClick={handleCreate}
              disabled={!name.trim() || createMutation.isPending}
              className="flex items-center gap-2 px-5 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm text-sm disabled:opacity-50"
            >
              {t("kb.create")}
            </button>
            <button
              type="button"
              onClick={onCancel}
              className="flex items-center gap-2 px-5 py-2 border border-border rounded-md hover:bg-accent transition-colors text-sm"
            >
              {t("kb.cancel")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
