"use client";

/**
 * NoteEditor — the right pane of /scratchpad (NOTES-001 §7).
 *
 * Controlled editor: owns only draft state derived from the note prop;
 * mutations (update/delete) run through the shared hooks; the parent
 * receives onSaved/onDeleted/onDiscuss callbacks. Preview reuses the
 * vendored markdownToHtml (no new dependency).
 *
 * Composition (RULE-04): the action bar lives in NoteEditorToolbar, the
 * metadata footer (tags + scope links) in NoteEditorLinks. This module
 * owns the draft state and the writing surface: title header, markdown
 * textarea, rendered preview.
 */

import { Eye, Pencil } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useDeleteNote, useUpdateNote } from "@/lib/hooks/useNotes";
import { markdownToHtml } from "@/lib/utils";
import type { Note, NoteTypeKey } from "@/types";
import { NoteEditorLinks, type NoteLinkDraft } from "./NoteEditorLinks";
import { NoteEditorToolbar } from "./NoteEditorToolbar";

export interface NoteEditorProps {
  readonly note: Note;
  readonly availableTags: readonly string[];
  readonly onSaved: () => void;
  readonly onDeleted: () => void;
  readonly onDiscuss: (noteId: string) => void;
}

/**
 * Preview typography via Tailwind child variants — the repo has no
 * @tailwindcss/typography plugin, so a dead `prose` class is replaced by
 * explicit selectors over markdownToHtml's output (h1–h3, p, strong, em).
 */
const PREVIEW_TYPOGRAPHY =
  "flex-1 overflow-y-auto p-4 text-sm leading-relaxed [&_em]:italic " +
  "[&_h1]:mb-3 [&_h1]:mt-6 [&_h1]:text-2xl [&_h1]:font-semibold " +
  "[&_h2]:mb-2 [&_h2]:mt-5 [&_h2]:text-xl [&_h2]:font-semibold " +
  "[&_h3]:mb-2 [&_h3]:mt-4 [&_h3]:text-lg [&_h3]:font-semibold " +
  "[&_p]:my-2.5 [&_strong]:font-semibold";

export function NoteEditor({
  note,
  availableTags,
  onSaved,
  onDeleted,
  onDiscuss,
}: NoteEditorProps) {
  const t = useTranslations("notes");
  const [title, setTitle] = useState(note.title ?? "");
  const [content, setContent] = useState(note.content);
  const [noteType, setNoteType] = useState<NoteTypeKey>(note.note_type);
  const [tags, setTags] = useState<string[]>([...note.tags]);
  const [links, setLinks] = useState<NoteLinkDraft>({
    novelId: note.novel_id ?? "",
    seriesId: note.series_id ?? "",
  });
  const [preview, setPreview] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  // A different note identity → fresh draft (the pane switched notes). The
  // effect is intentionally keyed by note.id, NOT the note object: background
  // refetches hand the editor a NEW object for the SAME note and must never
  // clobber the in-progress draft (binding T23→T26 review constraint). The
  // workspace additionally keys the editor by note.id for hard remounts.
  // biome-ignore lint/correctness/useExhaustiveDependencies: draft lifecycle is keyed by note identity — object-identity deps would reset drafts on background refetch (T23/T26 binding constraint).
  useEffect(() => {
    setTitle(note.title ?? "");
    setContent(note.content);
    setNoteType(note.note_type);
    setTags([...note.tags]);
    setLinks({ novelId: note.novel_id ?? "", seriesId: note.series_id ?? "" });
    setPreview(false);
    setConfirmOpen(false);
  }, [note.id]);

  const updateNote = useUpdateNote();
  const deleteNote = useDeleteNote();

  function handleSave() {
    updateNote.mutate(
      {
        id: note.id,
        body: {
          title: title.trim() || null,
          content,
          note_type: noteType,
          tags,
          // "" → explicit null clears a stored link (PATCH exclude_unset
          // semantics); never-set → undefined keeps the field untouched.
          novel_id: links.novelId || (note.novel_id ? null : undefined),
          series_id: links.seriesId || (note.series_id ? null : undefined),
        },
      },
      {
        onSuccess: () => onSaved(),
        onError: () => toast.error(t("editor.saveFailed")),
      },
    );
  }

  function handleDelete() {
    deleteNote.mutate(note.id, {
      onSuccess: () => {
        toast.success(t("editor.deleted"));
        setConfirmOpen(false);
        onDeleted();
      },
      onError: () => {
        toast.error(t("editor.deleteFailed"));
        setConfirmOpen(false);
      },
    });
  }

  return (
    <section aria-label={t("editor.contentLabel")} className="flex h-full flex-col bg-background">
      {/* Title reads as the note's heading; the whole row signals focus. */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-2 transition-colors focus-within:border-muted-foreground/40">
        <input
          type="text"
          value={title}
          data-testid="note-title-input"
          aria-label={t("editor.titlePlaceholder")}
          placeholder={t("editor.titlePlaceholder")}
          className="min-w-0 flex-1 bg-transparent text-lg font-medium tracking-tight text-foreground outline-none placeholder:font-normal placeholder:italic placeholder:text-muted-foreground"
          onChange={(event) => setTitle(event.target.value)}
        />
        <button
          type="button"
          data-testid="note-preview-toggle"
          aria-pressed={preview}
          title={preview ? t("editor.edit") : t("editor.preview")}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => setPreview((value) => !value)}
        >
          {preview ? (
            <Pencil className="size-4" aria-hidden="true" />
          ) : (
            <Eye className="size-4" aria-hidden="true" />
          )}
          <span className="sr-only">{preview ? t("editor.edit") : t("editor.preview")}</span>
        </button>
      </div>

      <NoteEditorToolbar
        noteType={noteType}
        onNoteTypeChange={setNoteType}
        onDiscuss={() => onDiscuss(note.id)}
        onSave={handleSave}
        onRequestDelete={() => setConfirmOpen(true)}
      />

      {preview ? (
        <div
          data-testid="note-preview"
          className={PREVIEW_TYPOGRAPHY}
          // biome-ignore lint/security/noDangerouslySetInnerHtml: markdownToHtml converts the vendored subset without escaping; the content is the user's own note (local-first, single user) — brief-documented decision (NOTES-001 §7).
          dangerouslySetInnerHTML={{ __html: markdownToHtml(content) }}
        />
      ) : (
        <textarea
          value={content}
          data-testid="note-content-input"
          aria-label={t("editor.contentLabel")}
          placeholder={t("editor.contentPlaceholder")}
          className="min-h-0 flex-1 resize-none bg-transparent p-4 font-mono text-sm leading-relaxed text-foreground outline-none placeholder:text-muted-foreground"
          onChange={(event) => setContent(event.target.value)}
        />
      )}

      <NoteEditorLinks
        links={links}
        onLinksChange={setLinks}
        tags={tags}
        onTagsChange={setTags}
        availableTags={availableTags}
      />

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("editor.deleteTitle")}
        description={t("editor.deleteDescription")}
        confirmLabel={t("editor.delete")}
        onConfirm={handleDelete}
        variant="destructive"
      />
    </section>
  );
}
