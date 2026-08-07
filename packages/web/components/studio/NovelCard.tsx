"use client";

import { Pencil, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { IconButton } from "@/components/ui/icon-button";
import { listItemVariants } from "@/lib/motion-variants";
import type { NovelSummary } from "@/types";

/**
 * NovelCard — presentational card for a single standalone novel
 * (Spec 1, Slice 4, Task 4.5).
 *
 * Extracted from the inline markup that used to live in NovelCardGrid so the
 * exact same card can sit in the mixed DashboardLibrary grid alongside
 * SeriesCards. Behaviour is unchanged: title / author / genre render, the whole
 * title block links to `/novel/[id]`, and the edit / delete IconButtons fire
 * their callbacks.
 *
 * Conventions matched to the former NovelCardGrid:
 *   - Entrance animation via `listItemVariants` from `@/lib/motion-variants`.
 *   - `data-testid="novel-card"` marker on the card root (ui-principles §18).
 *   - Edit / delete buttons reveal on hover/focus on `sm+` screens.
 */
export interface NovelCardProps {
  readonly novel: NovelSummary;
  readonly formatDate: (dateStr: string) => string;
  readonly onDelete: (id: string, title: string) => void;
  readonly onEdit: (id: string) => void;
  readonly isDeleting: boolean;
}

export function NovelCard({ novel, formatDate, onDelete, onEdit, isDeleting }: NovelCardProps) {
  const t = useTranslations("studio");

  return (
    <motion.div
      variants={listItemVariants}
      data-testid="novel-card"
      className="group bg-card border border-border rounded-lg p-6 hover:shadow-md transition-shadow relative"
    >
      {/* Edit button */}
      <IconButton
        label={t("dashboard.edit")}
        icon={Pencil}
        onClick={() => onEdit(novel.id)}
        variant="ghost"
        size="sm"
        className="absolute top-4 right-14 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100 transition-opacity"
        data-testid="edit-novel-btn"
      />

      {/* Delete button */}
      <IconButton
        label={t("dashboard.delete")}
        icon={Trash2}
        onClick={() => onDelete(novel.id, novel.title)}
        disabled={isDeleting}
        variant="ghost"
        size="sm"
        className="absolute top-4 right-4 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100 transition-opacity"
        data-testid="delete-novel-btn"
      />

      {/* Card content — clickable */}
      <a href={`/novel/${novel.id}`} className="block">
        <h3 className="text-lg font-medium mb-1 pr-8">{novel.title}</h3>
        <p className="text-sm text-muted-foreground mb-3">{novel.author}</p>

        <div className="flex items-center gap-2 mb-4">
          <span className="text-xs px-2 py-0.5 bg-muted rounded-md text-muted-foreground">
            {novel.genre}
          </span>
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {t("dashboard.lastEdited")} {formatDate(novel.updated_at)}
          </span>
        </div>
      </a>
    </motion.div>
  );
}
