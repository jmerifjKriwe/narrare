"use client";

import {
  DndContext,
  type DragEndEvent,
  DragOverlay,
  type DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { ChevronDown, ChevronUp, LayoutGrid, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { useStoryboard, useUpdateOutline } from "@/lib/hooks/usePlanning";
import { useEditorStore } from "@/lib/stores/editorStore";
import { cn } from "@/lib/utils";
import type { ChapterInStoryboard } from "@/types";
import { StoryboardScrollArrows } from "./StoryboardScrollArrows";
import { StoryboardStageColumn } from "./StoryboardStageColumn";
import { SyncStatusBadge } from "./SyncStatusBadge";

interface StoryboardPanelProps {
  novelId: string;
  /** When true, hides the collapse/expand header and border.
   *  Used when embedded inside PlanningPanel which manages its own header. */
  hideHeader?: boolean;
}

/** Find a chapter across all storyboard stages by its id. */
function findChapter(
  stages: { chapters: ChapterInStoryboard[] }[],
  chapterId: string,
): ChapterInStoryboard | undefined {
  for (const stage of stages) {
    const found = stage.chapters.find((ch) => ch.chapter_id === chapterId);
    if (found) return found;
  }
  return undefined;
}

export function StoryboardPanel({ novelId, hideHeader = false }: StoryboardPanelProps) {
  const t = useTranslations("studio");

  const storyboardOpen = useEditorStore((s) => s.storyboardOpen);
  const toggleStoryboard = useEditorStore((s) => s.toggleStoryboard);
  const setActiveChapterId = useEditorStore((s) => s.setActiveChapterId);

  const { data: storyboard, isLoading } = useStoryboard(novelId);
  const updateOutlineMutation = useUpdateOutline(novelId);

  const scrollRef = useRef<HTMLDivElement>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const [activeId, setActiveId] = useState<string | null>(null);
  const activeChapter =
    activeId && storyboard ? findChapter(storyboard.stages, activeId) : undefined;

  function handleDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.data.current?.chapterId ?? ""));
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;

    if (over) {
      const chapterId = String(active.data.current?.chapterId ?? "").replace("chapter-", "");
      const stageId = String(over.data.current?.stageId ?? "").replace("stage-", "");

      if (chapterId && stageId) {
        updateOutlineMutation.mutate({
          chapterId,
          data: { stage_assignment: stageId },
        });
      }
    }

    setActiveId(null);
  }

  function handleDragCancel() {
    setActiveId(null);
  }

  function handleNavigate(chapterId: string) {
    setActiveChapterId(chapterId);
  }

  const totalChapters =
    storyboard?.stages.reduce((sum, stage) => sum + stage.chapters.length, 0) ?? 0;

  // Collapsed state (skip when embedded in PlanningPanel)
  if (!storyboardOpen && !hideHeader) {
    return (
      <button
        type="button"
        onClick={toggleStoryboard}
        className="w-full flex items-center gap-3 px-6 py-2 border-b border-border bg-card hover:bg-accent transition-colors text-sm"
      >
        <LayoutGrid className="w-4 h-4 text-muted-foreground" />
        <span className="flex-1 text-left font-medium">
          {storyboard
            ? t("storyboard.collapsed", {
                structure: t(`wizard.storyStructure.${storyboard.structure_type}`),
                count: totalChapters,
              })
            : t("storyboard.title")}
        </span>
        <ChevronDown className="w-4 h-4 text-muted-foreground" />
      </button>
    );
  }

  // When embedded and collapsed, render nothing
  if (!storyboardOpen && hideHeader) {
    return null;
  }

  // Expanded state
  return (
    <div className={cn("w-full bg-card", !hideHeader && "border-b border-border")}>
      {/* Header — hidden when embedded in PlanningPanel */}
      {!hideHeader && (
        <div className="flex items-center gap-3 px-6 py-2 border-b border-border">
          <LayoutGrid className="w-4 h-4 text-muted-foreground" />
          <h3 className="text-sm font-medium flex-1">{t("storyboard.title")}</h3>
          <button
            type="button"
            onClick={toggleStoryboard}
            className="p-1 rounded hover:bg-accent transition-colors"
            aria-label={t("storyboard.collapse")}
          >
            <ChevronUp className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
      )}

      {/* Stage columns */}
      {isLoading ? (
        <div className="flex items-center justify-center py-6">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
      ) : storyboard ? (
        <div className="relative px-4 py-3">
          <StoryboardScrollArrows scrollContainerRef={scrollRef} />
          <div ref={scrollRef} className="flex gap-3 overflow-x-auto scrollbar-none">
            <DndContext
              sensors={sensors}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
              onDragCancel={handleDragCancel}
            >
              {storyboard.stages.map((stage) => (
                <StoryboardStageColumn
                  key={stage.stage_id}
                  stage={stage}
                  onNavigate={handleNavigate}
                  isDragActive={activeId !== null}
                  structureType={storyboard.structure_type}
                />
              ))}

              <DragOverlay dropAnimation={{ duration: 200, easing: "ease" }}>
                {activeId && activeChapter ? (
                  <div
                    className={cn(
                      "w-[100px] p-2 rounded-md border bg-card border-primary/50",
                      "shadow-xl ring-2 ring-primary/30 scale-105 opacity-90",
                      "flex flex-col gap-1.5 rotate-2",
                    )}
                  >
                    <p className="text-xs font-medium truncate">{activeChapter.title}</p>
                    <SyncStatusBadge status={activeChapter.sync_status} className="self-start" />
                    <p className="text-[10px] text-muted-foreground">
                      {t("editor.words", { count: activeChapter.word_count })}
                    </p>
                  </div>
                ) : null}
              </DragOverlay>
            </DndContext>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-center py-6 text-sm text-muted-foreground">
          {t("storyboard.title")}
        </div>
      )}

      {/* Mutation loading indicator */}
      {updateOutlineMutation.isPending && <div className={cn("h-0.5 bg-primary animate-pulse")} />}
    </div>
  );
}
