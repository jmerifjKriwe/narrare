"use client";

/**
 * QuickCapturePanel — slim capture form (NOTES-001 §7): the thought comes
 * FIRST (hero textarea), then the optional title / type / tag. Save creates
 * the note and toasts with an "Open in scratchpad" action; capture is fast,
 * curation lives on the page.
 *
 * Design (frontend-design, within the notes family language): the panel is
 * deliberately narrower than the chat drawer (max-w-sm vs max-w-md) —
 * "quick" reads as slim. The textarea carries the scratchpad's dashed
 * "fill me in" border (ScratchpadEmptyState's capture signal), the
 * shortcut hint is a physical kbd chip, and the eyebrow label echoes the
 * editor footer's rhythm so both surfaces read as one family.
 *
 * Focus: the provider wires this panel into `useDialogFocus`, whose initial
 * focus lands on the dialog's FIRST focusable element. The form body is
 * therefore first in DOM order (the header is pulled up visually with
 * `order-first`), which makes the textarea that first element — the field
 * you type the thought into gets focus the instant the panel opens.
 */

import { Loader2, StickyNote, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";
import { useCreateNote } from "@/lib/hooks/useNotes";
import { NOTE_TYPE_KEYS, type NoteTypeKey } from "@/types";

export interface QuickCapturePanelProps {
  readonly onClose: () => void;
}

export function QuickCapturePanel({ onClose }: QuickCapturePanelProps) {
  const t = useTranslations("notes");
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [tag, setTag] = useState("");
  const [noteType, setNoteType] = useState<NoteTypeKey>("idea");
  const createNote = useCreateNote();

  function resetDraft() {
    setTitle("");
    setText("");
    setTag("");
    setNoteType("idea");
  }

  function handleSave() {
    const content = text.trim();
    if (!content) return;
    createNote.mutate(
      {
        title: title.trim() || null,
        content,
        note_type: noteType,
        tags: tag.trim() ? [tag.trim()] : [],
      },
      {
        onSuccess: () => {
          toast.success(t("quickCapture.saved"), {
            action: {
              label: t("quickCapture.openInScratchpad"),
              onClick: () => router.push("/scratchpad"),
            },
          });
          resetDraft();
          onClose();
        },
        onError: () => toast.error(t("editor.saveFailed")),
      },
    );
  }

  const canSave = text.trim().length > 0 && !createNote.isPending;

  return (
    <div data-testid="quick-capture-panel" className="flex h-full flex-col">
      {/* Form body is FIRST in DOM so useDialogFocus's initial focus (first
          focusable) lands on the textarea; the header is pulled up VISUALLY
          via order-first. Visual order: header → body → footer. */}
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
        <textarea
          value={text}
          data-testid="qc-text"
          aria-label={t("quickCapture.textPlaceholder")}
          placeholder={t("quickCapture.textPlaceholder")}
          className="h-28 w-full resize-none rounded-md border border-dashed border-border bg-background p-2 text-sm font-normal text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          onChange={(event) => setText(event.target.value)}
        />

        <input
          type="text"
          value={title}
          data-testid="qc-title"
          aria-label={t("quickCapture.titlePlaceholder")}
          placeholder={t("quickCapture.titlePlaceholder")}
          className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm font-normal text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          onChange={(event) => setTitle(event.target.value)}
        />

        <div className="grid grid-cols-2 gap-2">
          <select
            value={noteType}
            data-testid="qc-type"
            aria-label={t("editor.typeLabel")}
            className="w-full cursor-pointer rounded-md border border-border bg-background px-2 py-1.5 text-sm font-normal text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            onChange={(event) => setNoteType(event.target.value as NoteTypeKey)}
          >
            {NOTE_TYPE_KEYS.map((key) => (
              <option key={key} value={key}>
                {t(`type.${key}`)}
              </option>
            ))}
          </select>

          <input
            type="text"
            value={tag}
            data-testid="qc-tag"
            aria-label={t("quickCapture.tagPlaceholder")}
            placeholder={t("quickCapture.tagPlaceholder")}
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm font-normal text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            onChange={(event) => setTag(event.target.value)}
          />
        </div>
      </div>

      <div className="order-first flex shrink-0 items-start justify-between gap-2 border-b border-border p-4">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-primary">
            <StickyNote className="size-4 shrink-0" aria-hidden="true" />
            <span className="text-[10px] font-semibold uppercase tracking-widest">
              {t("quickCapture.title")}
            </span>
          </p>
          <kbd className="mt-2 inline-block rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            {t("quickCapture.shortcutHint")}
          </kbd>
        </div>
        <button
          type="button"
          data-testid="qc-close"
          aria-label={t("quickCapture.close")}
          className="shrink-0 cursor-pointer rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={onClose}
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>

      <div className="shrink-0 space-y-2 border-t border-border p-4">
        <button
          type="button"
          data-testid="qc-save"
          disabled={!canSave}
          className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          onClick={handleSave}
        >
          {createNote.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          {t("quickCapture.save")}
        </button>
        <Link
          href="/scratchpad"
          data-testid="qc-scratchpad-link"
          className="block text-center text-xs text-muted-foreground underline-offset-4 hover:underline"
          onClick={onClose}
        >
          {t("quickCapture.openInScratchpad")}
        </Link>
      </div>
    </div>
  );
}
