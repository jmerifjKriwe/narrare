"use client"

import { useTranslations } from "next-intl"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { GripVertical, Plus } from "lucide-react"
import { chaptersApi } from "@/lib/api/client"
import { useEditorStore } from "@/lib/stores/editorStore"
import { cn } from "@/lib/utils"
import type { ChapterSummary } from "@/types"

interface ChapterSidebarProps {
  novelId: string
}

export function ChapterSidebar({ novelId }: ChapterSidebarProps) {
  const t = useTranslations("editor")
  const { chapters, activeChapterId, setChapters } = useEditorStore()
  const queryClient = useQueryClient()

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  const createChapter = useMutation({
    mutationFn: () => chaptersApi.create(novelId, { title: "" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chapters", novelId] }),
  })

  const reorderChapters = useMutation({
    mutationFn: (ids: string[]) => chaptersApi.reorder(novelId, ids),
    onSuccess: (updated) => {
      setChapters(updated)
      queryClient.setQueryData(["chapters", novelId], updated)
    },
  })

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = chapters.findIndex((c) => c.id === active.id)
    const newIndex = chapters.findIndex((c) => c.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return

    const reordered = [...chapters]
    const [moved] = reordered.splice(oldIndex, 1)
    reordered.splice(newIndex, 0, moved)
    setChapters(reordered)
    reorderChapters.mutate(reordered.map((c) => c.id))
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">{t("sidebar")}</span>
        <button
          className="sidebar-add"
          onClick={() => createChapter.mutate()}
          aria-label={t("addChapter")}
          title={t("addChapter")}
        >
          <Plus size={16} />
        </button>
      </div>

      <div className="sidebar-list">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={chapters.map((c) => c.id)}
            strategy={verticalListSortingStrategy}
          >
            {chapters.map((chapter) => (
              <SortableChapterItem
                key={chapter.id}
                chapter={chapter}
                novelId={novelId}
                isActive={chapter.id === activeChapterId}
              />
            ))}
          </SortableContext>
        </DndContext>

        {chapters.length === 0 && (
          <button
            className="sidebar-empty-cta"
            onClick={() => createChapter.mutate()}
          >
            <Plus size={14} />
            {t("addChapter")}
          </button>
        )}
      </div>

      <style jsx>{`
        .sidebar {
          width: var(--sidebar-width);
          border-right: 1px solid var(--color-border);
          background: var(--color-surface);
          display: flex;
          flex-direction: column;
          flex-shrink: 0;
          overflow: hidden;
        }
        .sidebar-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: var(--space-3) var(--space-4);
          border-bottom: 1px solid var(--color-border);
          flex-shrink: 0;
        }
        .sidebar-title {
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-tertiary);
        }
        .sidebar-add {
          width: 24px;
          height: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: var(--radius-sm);
          border: none;
          background: none;
          color: var(--color-text-secondary);
          cursor: pointer;
        }
        .sidebar-add:hover {
          background: var(--color-bg-tertiary);
          color: var(--color-text-primary);
        }
        .sidebar-list {
          flex: 1;
          overflow-y: auto;
          padding: var(--space-2) 0;
        }
        .sidebar-empty-cta {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          padding: var(--space-3) var(--space-4);
          color: var(--color-text-tertiary);
          font-size: 0.875rem;
          border: none;
          background: none;
          cursor: pointer;
          width: 100%;
        }
        .sidebar-empty-cta:hover { color: var(--color-text-secondary); }
      `}</style>
    </aside>
  )
}

interface SortableChapterItemProps {
  chapter: ChapterSummary
  novelId: string
  isActive: boolean
}

function SortableChapterItem({ chapter, novelId, isActive }: SortableChapterItemProps) {
  const t = useTranslations("editor")
  const { setActiveChapter } = useEditorStore()
  const queryClient = useQueryClient()

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: chapter.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  const handleClick = async () => {
    // Fetch full chapter on click
    const cached = queryClient.getQueryData<import("@/types").Chapter>(
      ["chapter", novelId, chapter.id]
    )
    if (cached) {
      setActiveChapter(cached)
    } else {
      const full = await chaptersApi.get(novelId, chapter.id)
      setActiveChapter(full)
    }
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn("chapter-item", isActive && "chapter-item--active")}
    >
      <button
        className="chapter-drag-handle"
        {...attributes}
        {...listeners}
        aria-label="Drag to reorder"
        tabIndex={-1}
      >
        <GripVertical size={14} />
      </button>

      <button className="chapter-button" onClick={handleClick} aria-current={isActive ? "true" : undefined}>
        <span className="chapter-title">
          {chapter.title || t("untitled")}
        </span>
        <span className="chapter-meta">
          {chapter.word_count > 0
            ? t("wordCount", { count: chapter.word_count.toLocaleString() })
            : ""}
        </span>
      </button>

      <style jsx>{`
        .chapter-item {
          display: flex;
          align-items: stretch;
          padding: 0 var(--space-2);
        }
        .chapter-item--active .chapter-button {
          background: var(--color-accent-light);
          color: var(--color-accent);
        }
        .chapter-drag-handle {
          display: flex;
          align-items: center;
          padding: var(--space-2) var(--space-1);
          color: var(--color-text-tertiary);
          border: none;
          background: none;
          cursor: grab;
          opacity: 0;
          border-radius: var(--radius-sm);
        }
        .chapter-item:hover .chapter-drag-handle { opacity: 1; }
        .chapter-button {
          flex: 1;
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          padding: var(--space-2) var(--space-3);
          border: none;
          background: none;
          cursor: pointer;
          border-radius: var(--radius-md);
          text-align: left;
          min-width: 0;
        }
        .chapter-button:hover { background: var(--color-bg-secondary); }
        .chapter-title {
          font-size: 0.875rem;
          font-weight: 500;
          color: var(--color-text-primary);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          width: 100%;
        }
        .chapter-meta {
          font-size: 0.75rem;
          color: var(--color-text-tertiary);
          margin-top: 2px;
        }
      `}</style>
    </div>
  )
}
