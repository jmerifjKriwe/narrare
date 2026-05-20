"use client";

import { DndContext, type DragEndEvent, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { ChevronDown, ChevronUp, LayoutGrid, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef } from "react";
import { useStoryboard, useUpdateOutline } from "@/lib/hooks/usePlanning";
import { useEditorStore } from "@/lib/stores/editorStore";
import { cn } from "@/lib/utils";
import { StoryboardScrollArrows } from "./StoryboardScrollArrows";
import { StoryboardStageColumn } from "./StoryboardStageColumn";

interface StoryboardPanelProps {
  novelId: string;
}

export function StoryboardPanel({ novelId }: StoryboardPanelProps) {
  const t = useTranslations("studio");

  const storyboardOpen = useEditorStore((s) => s.storyboardOpen);
  const toggleStoryboard = useEditorStore((s) => s.toggleStoryboard);
  const setActiveChapterId = useEditorStore((s) => s.setActiveChapterId);

  const { data: storyboard, isLoading } = useStoryboard(novelId);
  const updateOutlineMutation = useUpdateOutline(novelId);

  const scrollRef = useRef<HTMLDivElement>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;

    const chapterId = String(active.data.current?.chapterId ?? "").replace("chapter-", "");
    const stageId = String(over.data.current?.stageId ?? "").replace("stage-", "");

    if (chapterId && stageId) {
      updateOutlineMutation.mutate({
        chapterId,
        data: { stage_assignment: stageId },
      });
    }
  }

  function handleNavigate(chapterId: string) {
    setActiveChapterId(chapterId);
  }

  const totalChapters =
    storyboard?.stages.reduce((sum, stage) => sum + stage.chapters.length, 0) ?? 0;

  // Collapsed state
  if (!storyboardOpen) {
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

  // Expanded state
  return (
    <div className="w-full border-b border-border bg-card">
      {/* Header */}
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

      {/* Stage columns */}
      {isLoading ? (
        <div className="flex items-center justify-center py-6">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
      ) : storyboard ? (
        <div className="relative px-4 py-3">
          <StoryboardScrollArrows scrollContainerRef={scrollRef} />
          <div ref={scrollRef} className="flex gap-3 overflow-x-auto scrollbar-none">
            <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
              {storyboard.stages.map((stage) => (
                <StoryboardStageColumn
                  key={stage.stage_id}
                  stage={stage}
                  onNavigate={handleNavigate}
                />
              ))}
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
