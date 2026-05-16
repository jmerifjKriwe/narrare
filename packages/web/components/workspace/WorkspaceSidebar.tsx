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
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, FileText, Package, BarChart3, Settings, Plus } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { Route } from "next";
import { cn } from "@/lib/utils";
import { authApi, chaptersApi } from "@/lib/api/client";
import { useEditorStore } from "@/lib/stores/editorStore";
import type { ChapterSummary } from "@/types";

// ---------------------------------------------------------------------------
// Navigation tab definition
// ---------------------------------------------------------------------------

interface NavTab {
  key: string;
  href: (novelId: string) => Route;
  icon: React.ComponentType<{ className?: string }>;
  labelKey: string;
}

const NAV_TABS: NavTab[] = [
  {
    key: "editor",
    href: (id) => `/novel/${id}/editor` as Route,
    icon: FileText,
    labelKey: "editor",
  },
  {
    key: "worldbuilding",
    href: (id) => `/novel/${id}/worldbuilding` as Route,
    icon: Package,
    labelKey: "worldbuilding",
  },
  {
    key: "analysis",
    href: (id) => `/novel/${id}/analysis` as Route,
    icon: BarChart3,
    labelKey: "analysis",
  },
  {
    key: "settings",
    href: (id) => `/novel/${id}/settings` as Route,
    icon: Settings,
    labelKey: "settings",
  },
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface WorkspaceSidebarProps {
  novelId: string;
  activeTab: string;
}

// ---------------------------------------------------------------------------
// WorkspaceSidebar
// ---------------------------------------------------------------------------

export function WorkspaceSidebar({ novelId, activeTab }: WorkspaceSidebarProps) {
  const t = useTranslations("editor");
  const queryClient = useQueryClient();
  const { activeChapterId, setActiveChapterId } = useEditorStore();

  // Fetch chapters for the chapter list (only shown in editor view)
  const { data: chapters = [] } = useQuery({
    queryKey: ["chapters", novelId],
    queryFn: () => chaptersApi.list(novelId),
  });

  // Fetch user for avatar section
  const { data: user } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
  });

  // Chapter mutations
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

  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

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

  const displayName = user?.display_name || user?.email || "";
  const isEditorView = activeTab === "editor";

  return (
    <div className="w-72 bg-sidebar border-r border-sidebar-border flex flex-col h-full shrink-0">
      {/* Logo / Branding */}
      <div className="p-4 border-b border-sidebar-border">
        <Link href="/dashboard" className="flex items-center gap-3 no-underline">
          <div className="w-7 h-7 rounded-md bg-foreground flex items-center justify-center">
            <BookOpen className="w-4 h-4 text-background" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-foreground">{t("romanStudio")}</h1>
            <p className="text-xs text-muted-foreground">{t("romanStudioSubtitle")}</p>
          </div>
        </Link>
      </div>

      {/* Navigation tabs */}
      <nav className="p-3 space-y-0.5 border-b border-sidebar-border" aria-label="Workspace navigation">
        {NAV_TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          const Icon = tab.icon;
          return (
            <Link
              key={tab.key}
              href={tab.href(novelId)}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm w-full text-left no-underline",
                isActive
                  ? "bg-foreground text-background font-medium"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
              aria-current={isActive ? "page" : undefined}
            >
              <Icon className="w-4 h-4" />
              <span>{t(tab.labelKey)}</span>
            </Link>
          );
        })}
      </nav>

      {/* Chapter list — only visible in editor view */}
      {isEditorView && (
        <>
          <div className="px-3 pt-3 pb-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-3 mb-1">
              {t("chapters")}
            </p>
          </div>

          <div className="flex-1 overflow-y-auto px-3">
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={chapters.map((c) => c.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-1">
                  {chapters.map((chapter) => (
                    <SortableChapterItem
                      key={chapter.id}
                      chapter={chapter}
                      isActive={chapter.id === activeChapterId}
                      onSelect={setActiveChapterId}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          </div>

          {/* New chapter button */}
          <div className="mt-auto mx-3 mb-3">
            <button
              type="button"
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-foreground text-background rounded-md hover:opacity-90 transition-all cursor-pointer text-sm font-medium"
              onClick={() => createChapter.mutate()}
              aria-label={t("newChapter")}
            >
              <Plus className="w-4 h-4" />
              <span className="text-sm">{t("newChapter")}</span>
            </button>
          </div>
        </>
      )}

      {/* User avatar section — always visible at bottom */}
      <div className="border-t border-sidebar-border p-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-sidebar-accent flex items-center justify-center text-xs font-bold text-sidebar-accent-foreground shadow-inner">
            {displayName.charAt(0).toUpperCase()}
          </div>
          <span className="text-sm font-semibold text-foreground/90 truncate">
            {displayName}
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SortableChapterItem — DnD-enabled chapter list item
// ---------------------------------------------------------------------------

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
    <div ref={setNodeRef} style={style} className="mb-1 last:mb-0">
      <button
        type="button"
        className={cn(
          "w-full text-left px-3 py-2.5 rounded-md border border-border hover:bg-accent cursor-pointer",
          isActive
            ? "bg-accent"
            : "",
        )}
        onClick={() => onSelect(chapter.id)}
        aria-current={isActive ? "true" : undefined}
        {...attributes}
        {...listeners}
      >
        <div className="text-sm font-medium text-foreground truncate">
          {chapter.title || t("untitled")}
        </div>
        <div className="text-xs text-muted-foreground mt-0.5">
          {chapter.word_count > 0
            ? t("wordCount", { count: chapter.word_count.toLocaleString() })
            : t("wordCount", { count: 0 })}
        </div>
      </button>
    </div>
  );
}
