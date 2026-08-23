"use client";

/**
 * ScratchpadEmptyState — the /scratchpad right pane when no note exists yet
 * (NOTES-001 §7 "empty state: single capture card creating the first note").
 *
 * Owns only its capture draft (text + type); the CREATE mutation stays with
 * the parent (ScratchpadWorkspace) via onCapture — data lives with the
 * orchestrator, presentation here.
 *
 * Design (frontend-design, within the established notes language): the one
 * `border-dashed` surface in the scratchpad — a physical "fill this in"
 * card — on a quiet `bg-muted/30` backdrop, entering via the central
 * dialogVariants. The TYPE micro-label mirrors the editor footer's label
 * rhythm so both panes read as one family.
 */

import { StickyNote } from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { dialogVariants } from "@/lib/motion-variants";
import { NOTE_TYPE_KEYS, type NoteTypeKey } from "@/types";

export interface ScratchpadEmptyStateProps {
  /** Fires with the trimmed draft + chosen type; parent runs the mutation. */
  readonly onCapture: (text: string, noteType: NoteTypeKey) => void;
  /** True while the create mutation is in flight (disables the save button). */
  readonly pending: boolean;
}

export function ScratchpadEmptyState({ onCapture, pending }: ScratchpadEmptyStateProps) {
  const t = useTranslations("notes");
  const [draft, setDraft] = useState("");
  const [noteType, setNoteType] = useState<NoteTypeKey>("idea");

  const canSave = draft.trim().length > 0 && !pending;

  return (
    <section
      data-testid="scratchpad-empty"
      aria-label={t("empty.title")}
      className="flex h-full items-center justify-center bg-muted/30 p-6"
    >
      <motion.div
        variants={dialogVariants}
        initial="hidden"
        animate="visible"
        className="w-full max-w-md rounded-xl border border-dashed border-border bg-card p-6 shadow-sm"
      >
        <p className="flex items-center gap-2 text-primary">
          <StickyNote className="size-5" aria-hidden="true" />
          <span className="text-[10px] font-semibold uppercase tracking-widest">
            {t("page.title")}
          </span>
        </p>
        <h2 className="mt-2 text-lg font-medium tracking-tight text-foreground">
          {t("empty.title")}
        </h2>
        <p className="mt-1 text-sm font-normal text-muted-foreground">{t("empty.description")}</p>

        <div className="mt-5 space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            {t("editor.typeLabel")}
          </p>
          <select
            value={noteType}
            data-testid="empty-capture-type"
            aria-label={t("editor.typeLabel")}
            className="w-full cursor-pointer rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            onChange={(event) => setNoteType(event.target.value as NoteTypeKey)}
          >
            {NOTE_TYPE_KEYS.map((key) => (
              <option key={key} value={key}>
                {t(`type.${key}`)}
              </option>
            ))}
          </select>

          <textarea
            value={draft}
            data-testid="empty-capture-text"
            aria-label={t("empty.cta")}
            placeholder={t("editor.contentPlaceholder")}
            className="h-24 w-full resize-none rounded-md border border-border bg-background p-2 text-sm font-normal text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            onChange={(event) => setDraft(event.target.value)}
          />

          <button
            type="button"
            data-testid="empty-capture-save"
            disabled={!canSave}
            className="w-full cursor-pointer rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => onCapture(draft.trim(), noteType)}
          >
            {t("empty.cta")}
          </button>
        </div>
      </motion.div>
    </section>
  );
}
