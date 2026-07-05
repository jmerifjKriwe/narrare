"use client";

import { BookOpen, Pencil, Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { IconButton } from "@/components/ui/icon-button";
import type { NovelSummary } from "@/types";

/**
 * NovelCardGrid — Novel cards grid with loading, empty, and populated states.
 *
 * Includes individual novel cards with edit/delete actions and a "new novel" card.
 * Extracted from DashboardView.tsx (RULE-04).
 */

interface NovelCardGridProps {
  novels: NovelSummary[];
  isLoading: boolean;
  onDelete: (id: string, title: string) => void;
  onEdit: (id: string) => void;
  onNew: () => void;
  isDeleting: boolean;
  formatDate: (dateStr: string) => string;
}

export function NovelCardGrid({
  novels,
  isLoading,
  onDelete,
  onEdit,
  onNew,
  isDeleting,
  formatDate,
}: NovelCardGridProps) {
  const t = useTranslations("studio");

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-card border border-border rounded-lg p-6 animate-pulse">
            <div className="h-6 bg-muted rounded mb-2 w-3/4" />
            <div className="h-4 bg-muted rounded mb-4 w-1/2" />
            <div className="h-4 bg-muted rounded w-1/3" />
          </div>
        ))}
      </div>
    );
  }

  if (novels.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
        <BookOpen className="w-16 h-16 mb-4 opacity-10" />
        <p className="text-lg mb-1">{t("dashboard.emptyTitle")}</p>
        <p className="text-sm">{t("dashboard.emptySubtitle")}</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {novels.map((novel: NovelSummary) => (
        <div
          key={novel.id}
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
        </div>
      ))}

      {/* New novel card */}
      <button
        type="button"
        data-testid="new-novel-btn"
        onClick={onNew}
        className="flex flex-col items-center justify-center bg-card border-2 border-dashed border-border rounded-lg p-6 hover:border-primary/50 hover:bg-accent transition-colors min-h-[180px]"
      >
        <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-3">
          <Plus className="w-5 h-5 text-muted-foreground" />
        </div>
        <span className="text-sm font-medium text-muted-foreground">{t("dashboard.newNovel")}</span>
      </button>
    </div>
  );
}
