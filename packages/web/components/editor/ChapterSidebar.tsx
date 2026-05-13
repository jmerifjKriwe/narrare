"use client";

import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GripVertical, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { chaptersApi } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { ChapterSummary } from "@/types";

interface ChapterSidebarProps {
  novelId: string;
  chapters: ChapterSummary[];
  activeChapterId: string | null;
  onChapterSelect: (chapterId: string) => void;
}

export function ChapterSidebar({
  novelId,
  chapters,
  activeChapterId,
  onChapterSelect,
}: ChapterSidebarProps) {
  const t = useTranslations("editor");
  const queryClient = useQueryClient();

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const createChapter = useMutation({
    mutationFn: () => chaptersApi.create(novelId, { title: "" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chapters", novelId] }),
  });

  const reorderChapters = useMutation({
    mutationFn: (ids: string[]) => chaptersApi.reorder(novelId, ids),
    onSuccess: (updated) => {
      queryClient.setQueryData(["chapters", novelId], updated);
    },
  });

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = chapters.findIndex((c) => c.id === active.id);
    const newIndex = chapters.findIndex((c) => c.id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;

    const reordered = [...chapters];
    const [moved] = reordered.splice(oldIndex, 1);
    reordered.splice(newIndex, 0, moved);
    // Optimistic update: write to cache immediately, mutation will confirm
    queryClient.setQueryData(["chapters", novelId], reordered);
    reorderChapters.mutate(reordered.map((c) => c.id));
  };

  return (
    <aside className="w-[var(--sidebar-width)] border-r border-[var(--color-border)] bg-[var(--color-surface)] flex flex-col shrink-0 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)] shrink-0">
        <span className="text-[0.6875rem] font-semibold uppercase tracking-[0.15em] text-[var(--color-text-tertiary)]">
          {t("sidebar")}
        </span>
        <button
          type="button"
          className="w-6 h-6 flex items-center justify-center rounded-[var(--radius-sm)] border-none bg-transparent text-[var(--color-text-secondary)] cursor-pointer hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]"
          onClick={() => createChapter.mutate()}
          aria-label={t("addChapter")}
          title={t("addChapter")}
        >
          <Plus size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={chapters.map((c) => c.id)} strategy={verticalListSortingStrategy}>
            {chapters.map((chapter) => (
              <SortableChapterItem
                key={chapter.id}
                chapter={chapter}
                isActive={chapter.id === activeChapterId}
                onSelect={onChapterSelect}
              />
            ))}
          </SortableContext>
        </DndContext>

        {chapters.length === 0 && (
          <button
            type="button"
            className="flex items-center gap-2 py-3 px-4 text-[var(--color-text-tertiary)] text-sm border-none bg-transparent cursor-pointer w-full hover:text-[var(--color-text-secondary)]"
            onClick={() => createChapter.mutate()}
          >
            <Plus size={14} />
            {t("addChapter")}
          </button>
        )}
      </div>
    </aside>
  );
}

interface SortableChapterItemProps {
  chapter: ChapterSummary;
  isActive: boolean;
  onSelect: (chapterId: string) => void;
}

function SortableChapterItem({ chapter, isActive, onSelect }: SortableChapterItemProps) {
  const t = useTranslations("editor");

  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: chapter.id,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="group flex items-stretch px-2">
      <button
        type="button"
        className="flex items-center py-2 px-1 text-[var(--color-text-tertiary)] border-none bg-transparent cursor-grab opacity-0 rounded-[var(--radius-sm)] group-hover:opacity-100"
        {...attributes}
        {...listeners}
        aria-label="Drag to reorder"
        tabIndex={-1}
      >
        <GripVertical size={14} />
      </button>

      <button
        type="button"
        className={cn(
          "flex-1 flex flex-col items-start py-2.5 px-3 border-none bg-transparent cursor-pointer rounded-lg text-left min-w-0 transition-all duration-200 relative",
          "hover:bg-[var(--color-bg-secondary)]",
          isActive && "bg-[var(--color-accent-light)]/60",
        )}
        onClick={() => onSelect(chapter.id)}
        aria-current={isActive ? "true" : undefined}
      >
        {isActive && (
          <div className="absolute left-0 top-1 bottom-1 w-[3px] rounded-full bg-[var(--color-accent)]" />
        )}
        <span
          className={cn(
            "text-[0.8125rem] font-medium text-[var(--color-text-primary)] overflow-hidden text-ellipsis whitespace-nowrap w-full pl-2",
            isActive && "font-semibold",
          )}
          style={isActive ? { fontFamily: "var(--font-display)" } : undefined}
        >
          {chapter.title || t("untitled")}
        </span>
        <span className="text-[0.6875rem] text-[var(--color-text-tertiary)] mt-0.5 pl-2 font-[family-name:var(--font-mono)]">
          {chapter.word_count > 0
            ? t("wordCount", { count: chapter.word_count.toLocaleString() })
            : ""}
        </span>
      </button>
    </div>
  );
}
