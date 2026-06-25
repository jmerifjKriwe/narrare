"use client";

import { Clock, LayoutGrid, Users } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useEditorStore } from "@/lib/stores/editorStore";
import { cn } from "@/lib/utils";
import { CharacterArcPanel } from "./CharacterArcPanel";
import { StoryboardPanel } from "./StoryboardPanel";
import { TimelinePanel } from "./timeline/TimelinePanel";

type PlanningTab = "storyboard" | "timeline" | "characterArc";

interface PlanningPanelProps {
  novelId: string;
}

/** Container that switches between Storyboard and Timeline views. */
export function PlanningPanel({ novelId }: PlanningPanelProps) {
  const t = useTranslations("studio");
  const tTimeline = useTranslations("timeline");
  const storyboardOpen = useEditorStore((s) => s.storyboardOpen);
  const toggleStoryboard = useEditorStore((s) => s.toggleStoryboard);
  const [activeTab, setActiveTab] = useState<PlanningTab>("storyboard");

  // Collapsed state
  if (!storyboardOpen) {
    return (
      <button
        type="button"
        onClick={toggleStoryboard}
        className="w-full flex items-center gap-3 px-6 py-2 border-b border-border bg-card hover:bg-accent transition-colors text-sm"
      >
        <LayoutGrid className="w-4 h-4 text-muted-foreground" />
        <span className="flex-1 text-left font-medium">{t("storyboard.title")}</span>
      </button>
    );
  }

  return (
    <div className="w-full border-b border-border bg-card">
      {/* Header with tabs */}
      <div className="flex items-center gap-3 px-6 py-2 border-b border-border">
        <button
          type="button"
          onClick={() => setActiveTab("storyboard")}
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded transition-colors",
            activeTab === "storyboard"
              ? "bg-[var(--color-accent)] text-white"
              : "text-muted-foreground hover:bg-[var(--color-bg-secondary)]",
          )}
        >
          <LayoutGrid className="w-3.5 h-3.5" />
          {t("storyboard.title")}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("timeline")}
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded transition-colors",
            activeTab === "timeline"
              ? "bg-[var(--color-accent)] text-white"
              : "text-muted-foreground hover:bg-[var(--color-bg-secondary)]",
          )}
        >
          <Clock className="w-3.5 h-3.5" />
          {tTimeline("title")}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("characterArc")}
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded transition-colors",
            activeTab === "characterArc"
              ? "bg-[var(--color-accent)] text-white"
              : "text-muted-foreground hover:bg-[var(--color-bg-secondary)]",
          )}
        >
          <Users className="w-3.5 h-3.5" />
          {t("characterArc.title")}
        </button>
      </div>

      {/* Tab content */}
      {activeTab === "storyboard" && <StoryboardPanel novelId={novelId} hideHeader />}
      {activeTab === "timeline" && <TimelinePanel novelId={novelId} />}
      {activeTab === "characterArc" && <CharacterArcPanel novelId={novelId} />}
    </div>
  );
}
