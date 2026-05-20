"use client";

import { useDroppable } from "@dnd-kit/core";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { ChapterInStoryboard, StoryboardStageResponse } from "@/types";
import { StoryboardCard } from "./StoryboardCard";

interface StoryboardStageColumnProps {
  stage: StoryboardStageResponse;
  onNavigate: (chapterId: string) => void;
  isDragActive?: boolean;
  structureType: string;
}

export function StoryboardStageColumn({
  stage,
  onNavigate,
  isDragActive = false,
  structureType,
}: StoryboardStageColumnProps) {
  const t = useTranslations("studio");

  const { isOver, setNodeRef } = useDroppable({
    id: `stage-${stage.stage_id}`,
    data: { stageId: stage.stage_id },
  });

  /** Try i18n lookup for stage name, fall back to server-provided name. */
  function getStageName(): string {
    try {
      return t(`storyboard.stages.${structureType}.${stage.stage_id}` as Parameters<typeof t>[0]);
    } catch {
      return stage.stage_name;
    }
  }

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex-shrink-0 w-[140px] flex flex-col gap-2 p-2 rounded-lg border-2 min-h-[200px]",
        "transition-colors",
        isOver
          ? "border-primary bg-primary/5 shadow-[0_0_8px_rgba(var(--color-primary),0.15)]"
          : isDragActive
            ? "border-primary/40 border-dashed bg-card"
            : "border-border bg-card",
      )}
    >
      {/* Stage header */}
      <h4 className="text-xs font-semibold text-center truncate px-1">{getStageName()}</h4>

      {/* Chapter cards */}
      <div className="flex flex-col gap-1.5 flex-1">
        {stage.chapters.map((chapter: ChapterInStoryboard) => (
          <StoryboardCard key={chapter.chapter_id} chapter={chapter} onNavigate={onNavigate} />
        ))}

        {/* Empty drop zone */}
        {stage.chapters.length === 0 && (
          <div className="flex-1 flex items-center justify-center border-2 border-dashed border-border rounded-md">
            <span className="text-xs text-muted-foreground">{t("storyboard.emptySlot")}</span>
          </div>
        )}
      </div>
    </div>
  );
}
