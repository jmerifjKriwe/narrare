"use client";

/**
 * NoteEditorToolbar — the action bar between header and writing surface
 * (NOTES-001 §7): note type select, discuss-in-chat trigger, save, delete
 * trigger.
 *
 * Purely presentational (RULE-06): every control delegates upward. The
 * delete button only REQUESTS deletion — the ConfirmDialog owned by
 * NoteEditor gates the actual mutation.
 */

import { MessageCircle, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { NOTE_TYPE_KEYS, type NoteTypeKey } from "@/types";

export interface NoteEditorToolbarProps {
  readonly noteType: NoteTypeKey;
  readonly onNoteTypeChange: (next: NoteTypeKey) => void;
  readonly onDiscuss: () => void;
  readonly onSave: () => void;
  readonly onRequestDelete: () => void;
}

export function NoteEditorToolbar({
  noteType,
  onNoteTypeChange,
  onDiscuss,
  onSave,
  onRequestDelete,
}: NoteEditorToolbarProps) {
  const t = useTranslations("notes");

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2 text-sm">
      <label className="flex items-center gap-1.5">
        <span className="text-muted-foreground">{t("editor.typeLabel")}</span>
        <select
          value={noteType}
          data-testid="note-type-select"
          aria-label={t("editor.typeLabel")}
          className="rounded-md border border-border bg-background px-2 py-1 text-foreground transition-colors hover:border-muted-foreground/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onChange={(event) => onNoteTypeChange(event.target.value as NoteTypeKey)}
        >
          {NOTE_TYPE_KEYS.map((key) => (
            <option key={key} value={key}>
              {t(`type.${key}`)}
            </option>
          ))}
        </select>
      </label>

      <button
        type="button"
        data-testid="note-discuss-button"
        className="flex items-center gap-1.5 rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={onDiscuss}
      >
        <MessageCircle className="size-4" aria-hidden="true" />
        {t("editor.discuss")}
      </button>

      <button
        type="button"
        data-testid="note-save-button"
        className="rounded-md bg-primary px-3 py-1 font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={onSave}
      >
        {t("editor.save")}
      </button>

      <button
        type="button"
        data-testid="note-delete-button"
        className="ml-auto flex items-center gap-1.5 rounded-md p-1.5 text-destructive transition-colors hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        title={t("editor.delete")}
        onClick={onRequestDelete}
      >
        <Trash2 className="size-4" aria-hidden="true" />
        <span className="sr-only">{t("editor.delete")}</span>
      </button>
    </div>
  );
}
