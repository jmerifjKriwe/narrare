"use client";

import { useDraggable } from "@dnd-kit/core";
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
      {...attributes}
      {...listeners}
      className={cn(
        "w-[100px] p-2 rounded-md border bg-card border-border cursor-pointer",
        "hover:shadow-sm transition-shadow",
        "flex flex-col gap-1.5 text-left",
        isDragging && "opacity-30 border-dashed border-muted-foreground/30",
      )}
    >
      <button
        type="button"
        onClick={() => onNavigate(chapter.chapter_id)}
        className="text-left w-full"
        aria-label={chapter.title}
      >
        <p className="text-xs font-medium truncate">{chapter.title}</p>
      </button>
      <SyncStatusBadge status={chapter.sync_status} className="self-start" />
      <p className="text-[10px] text-muted-foreground">
        {t("editor.words", { count: chapter.word_count })}
      </p>
    </div>
  );
}
