"use client";

import { Clapperboard, Clock, LayoutGrid, Users } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";
import { PanelTabs } from "@/components/ui/panel-tabs";
import { useEditorStore } from "@/lib/stores/editorStore";
import { searchParamsHref, setOptionalSearchParam } from "@/lib/url-state/searchParams";
import { CharacterArcPanel } from "./CharacterArcPanel";
import {
  type PlanningTab,
  parsePlanningUrlState,
  serializePlanningUrlState,
} from "./planningUrlState";
import { ScenePlanEditor } from "./ScenePlanEditor";
import { StoryboardPanel } from "./StoryboardPanel";
import { TimelinePanel } from "./timeline/TimelinePanel";

interface PlanningPanelProps {
  novelId: string;
}

/** Container that switches between Storyboard and Timeline views. */
export function PlanningPanel({ novelId }: PlanningPanelProps) {
  const t = useTranslations("studio");
  const tTimeline = useTranslations("timeline");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsSnapshot = searchParams.toString();
  const storyboardOpen = useEditorStore((s) => s.storyboardOpen);
  const toggleStoryboard = useEditorStore((s) => s.toggleStoryboard);
  const activeChapterId = useEditorStore((s) => s.activeChapterId);
  const urlState = useMemo(
    () => parsePlanningUrlState(new URLSearchParams(searchParamsSnapshot)),
    [searchParamsSnapshot],
  );
  const [activeTab, setActiveTab] = useState<PlanningTab>(urlState.tab);
  const isPlanningOpen = storyboardOpen || urlState.open;
  const previousSearchParamsSnapshotRef = useRef(searchParamsSnapshot);

  const pushPlanningState = (open: boolean, tab: PlanningTab) => {
    const serializedState = serializePlanningUrlState({ open, tab });
    const nextParams = new URLSearchParams(searchParamsSnapshot);
    nextParams.delete("planning");
    nextParams.delete("planningTab");
    const planningParam = serializedState.get("planning");
    const planningTabParam = serializedState.get("planningTab");
    const mergedParams = setOptionalSearchParam(
      setOptionalSearchParam(nextParams, "planning", planningParam),
      "planningTab",
      planningTabParam,
    );
    router.push(searchParamsHref(pathname, mergedParams), { scroll: false });
  };

  useEffect(() => {
    setActiveTab(urlState.tab);
    const previousParams = new URLSearchParams(previousSearchParamsSnapshotRef.current);
    const currentParams = new URLSearchParams(searchParamsSnapshot);
    const planningParamChanged = previousParams.get("planning") !== currentParams.get("planning");
    previousSearchParamsSnapshotRef.current = searchParamsSnapshot;

    if (urlState.open && !storyboardOpen) toggleStoryboard();
    if (!urlState.open && storyboardOpen && planningParamChanged) toggleStoryboard();
  }, [searchParamsSnapshot, storyboardOpen, toggleStoryboard, urlState.open, urlState.tab]);

  // Collapsed state
  if (!isPlanningOpen) {
    return (
      <button
        type="button"
        onClick={() => {
          if (!storyboardOpen) toggleStoryboard();
          pushPlanningState(true, activeTab);
        }}
        className="w-full flex items-center gap-3 px-6 py-2 border-b border-border bg-card hover:bg-accent transition-colors text-sm"
      >
        <LayoutGrid className="w-4 h-4 text-muted-foreground" />
        <span className="flex-1 text-left font-medium">{t("storyboard.title")}</span>
      </button>
    );
  }

  return (
    <section className="w-full border-b border-border bg-card" aria-label={t("storyboard.title")}>
      {/*
        Scenes / Storyboard / Timeline / Character Arc tabs. The bounded
        viewport height lets PanelTabs' tabpanel scroll internally (mirroring
        the previous max-h content region). `value`/`onValueChange` stay wired
        to the existing planningUrlState adapter (combined open+tab URL scheme).
        The scenes tab hosts the PLAN-001 ScenePlanEditor for the active chapter.
      */}
      <div className="h-[45vh] lg:h-[36vh]">
        <PanelTabs
          ariaLabel={t("storyboard.title")}
          value={activeTab}
          onValueChange={(id) => {
            const tab = id as PlanningTab;
            setActiveTab(tab);
            pushPlanningState(true, tab);
          }}
          tabs={[
            {
              id: "storyboard",
              label: t("storyboard.title"),
              icon: LayoutGrid,
              content: <StoryboardPanel novelId={novelId} hideHeader />,
            },
            {
              id: "scenes",
              label: t("planning.scenes.title"),
              icon: Clapperboard,
              content: <ScenePlanEditor novelId={novelId} chapterId={activeChapterId} />,
            },
            {
              id: "timeline",
              label: tTimeline("title"),
              icon: Clock,
              content: <TimelinePanel novelId={novelId} />,
            },
            {
              id: "characterArc",
              label: t("characterArc.title"),
              icon: Users,
              content: <CharacterArcPanel novelId={novelId} />,
            },
          ]}
        />
      </div>
    </section>
  );
}
