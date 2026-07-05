"use client";

import { useDraggable } from "@dnd-kit/core";
import { GripVertical } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { ChapterInStoryboard } from "@/types";
import { SyncStatusBadge } from "./SyncStatusBadge";

interface StoryboardCardProps {
  chapter: ChapterInStoryboard;
  onNavigate: (chapterId: string) => void;
}

export function StoryboardCard({ chapter, onNavigate }: StoryboardCardProps) {
  const t = useTranslations("studio");

  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `chapter-${chapter.chapter_id}`,
    data: { chapterId: chapter.chapter_id },
  });

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "w-[100px] rounded-md border bg-card border-border",
        "flex flex-col gap-1.5 text-left",
        isDragging && "opacity-30 border-dashed border-muted-foreground/30",
      )}
    >
      <button
        type="button"
        onClick={() => onNavigate(chapter.chapter_id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onNavigate(chapter.chapter_id);
          }
        }}
        className="text-left w-full px-2 pt-2 hover:bg-accent transition-colors rounded-t-md"
        aria-label={t("planning.openChapter", { title: chapter.title })}
      >
        <p className="text-xs font-medium truncate">{chapter.title}</p>
      </button>
      <SyncStatusBadge status={chapter.sync_status} className="self-start px-2" />
      <p className="text-[10px] text-muted-foreground px-2 pb-1">
        {t("editor.words", { count: chapter.word_count })}
      </p>
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="flex items-center justify-center py-1 border-t border-border text-muted-foreground hover:text-foreground hover:bg-accent transition-colors cursor-grab active:cursor-grabbing rounded-b-md focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        aria-label={t("planning.dragChapter", { title: chapter.title })}
      >
        <GripVertical className="w-3 h-3" aria-hidden="true" />
      </button>
    </div>
  );
}
