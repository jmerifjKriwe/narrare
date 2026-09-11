"use client";

/**
 * NoteList — selectable list of notes (NOTES-001 §7).
 *
 * Presentational: parent owns data + selection. Uses the central Motion
 * variants; setupTests neutralizes motion in tests.
 */

import { motion } from "motion/react";
import { useFormatter, useTranslations } from "next-intl";
import { listContainerVariants, listItemVariants } from "@/lib/motion-variants";
import { type Note, noteDisplayTitle } from "@/types";

export interface NoteListProps {
  readonly notes: readonly Note[];
  readonly selectedId: string | null;
  readonly onSelect: (noteId: string) => void;
}

export function NoteList({ notes, selectedId, onSelect }: NoteListProps) {
  const t = useTranslations("notes");
  // Locale-aware date via next-intl (app locale, medium date style — same ICU
  // style as the series drift snapshot hint), never the browser locale.
  const format = useFormatter();

  if (notes.length === 0) {
    return (
      <p data-testid="note-list-empty" className="p-8 text-center text-sm text-muted-foreground">
        {t("list.noResults")}
      </p>
    );
  }

  return (
    <motion.ul
      variants={listContainerVariants}
      initial="hidden"
      animate="visible"
      aria-label={t("page.title")}
      className="flex-1 overflow-y-auto"
    >
      {notes.map((note) => {
        const displayTitle = noteDisplayTitle(note) || t("list.untitled");
        const active = note.id === selectedId;
        return (
          <motion.li key={note.id} variants={listItemVariants}>
            <button
              type="button"
              data-testid={`note-list-item-${note.id}`}
              aria-current={active ? "true" : undefined}
              onClick={() => onSelect(note.id)}
              className={`w-full cursor-pointer border-b border-border px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset ${
                active ? "bg-accent" : "hover:bg-accent/50"
              }`}
            >
              <span className="flex items-center gap-2">
                <span className="rounded bg-secondary px-1.5 py-0.5 text-xs font-normal text-secondary-foreground">
                  {t(`type.${note.note_type}`)}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm font-medium">{displayTitle}</span>
              </span>
              {note.tags.length > 0 && (
                <span className="mt-1 flex flex-wrap gap-1">
                  {note.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full bg-muted px-2 py-0.5 text-xs font-normal"
                    >
                      {tag}
                    </span>
                  ))}
                </span>
              )}
              <span className="mt-1 block text-xs font-normal text-muted-foreground">
                {t("list.updated", {
                  date: format.dateTime(new Date(note.updated_at), { dateStyle: "medium" }),
                })}
              </span>
            </button>
          </motion.li>
        );
      })}
    </motion.ul>
  );
}
