"use client";

/**
 * Compact scene-plan panel for the editor right panel (PLAN-001 spec §8.2).
 *
 * Lists the active chapter's scene plans (status chips, title, purpose) and
 * reuses the Planning tab's {@link SceneCard} (read mode + {@link SceneForm}
 * on expand) for inline edits. Field edits stay LOCAL until "Save" (aggregate
 * PUT via useSaveScenePlans); reorder/remove persist immediately — mirroring
 * ScenePlanEditor semantics. Full management (add / AI draft / characters)
 * lives in the Planning tab, reachable via "Open full planner" (planning URL
 * state; the PlanningPanel effect opens the storyboard strip on navigation).
 */

import { Clapperboard, Loader2, Save, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useSaveScenePlans, useScenePlans } from "@/lib/hooks/usePlanning";
import { searchParamsHref } from "@/lib/url-state/searchParams";
import type { ScenePlan } from "@/types/planning";
import { SceneCard } from "../planning/SceneCard";

interface ScenePlanPanelProps {
  readonly novelId: string;
  readonly chapterId: string;
  readonly onClose: () => void;
}

/** Renumber positions 1..N in list order (server diff-syncs by id).
 * Local twin of ScenePlanEditor's module-private helper. */
function withPositions(scenes: ScenePlan[]): ScenePlan[] {
  return scenes.map((scene, index) =>
    scene.position === index + 1 ? scene : { ...scene, position: index + 1 },
  );
}

export function ScenePlanPanel({ novelId, chapterId, onClose }: ScenePlanPanelProps) {
  const t = useTranslations("studio.planning.scenes");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { data: aggregate, isLoading } = useScenePlans(novelId, chapterId || null);
  const save = useSaveScenePlans(novelId);

  // The server aggregate is the source of truth after every fetch/invalidation.
  const [scenes, setScenes] = useState<ScenePlan[]>([]);
  useEffect(() => {
    if (aggregate) setScenes(aggregate.scenes);
  }, [aggregate]);

  /** "Open full planner" → Planning tab (scenes) via URL state, panel closes. */
  function openFullPlanner() {
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.set("planning", "1");
    nextParams.set("planningTab", "scenes");
    router.push(searchParamsHref(pathname, nextParams), { scroll: false });
    onClose();
  }

  function persist(next: ScenePlan[]) {
    setScenes(next);
    save.mutate({ chapterId, data: { scenes: withPositions(next) } });
  }

  function move(index: number, dir: -1 | 1) {
    const next = [...scenes];
    const target = index + dir;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    persist(next);
  }

  const header = (
    <div className="flex items-center justify-between px-4 py-3 border-b border-border">
      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <Clapperboard className="w-4 h-4 text-primary" aria-hidden="true" />
        <span>{t("title")}</span>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="p-1.5 rounded-md hover:bg-accent transition-colors"
        aria-label={t("closePanel")}
      >
        <X className="w-4 h-4" aria-hidden="true" />
      </button>
    </div>
  );

  if (!chapterId) {
    return (
      <div className="flex flex-col h-full">
        {header}
        <p className="text-xs text-muted-foreground p-4">{t("noChapter")}</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-col h-full">
        {header}
        <div className="flex items-center justify-center py-4">
          {/* role="status" announces via its text content (sr-only), robust
              across AT — the SVG itself stays aria-hidden like its siblings. */}
          <span role="status">
            <span className="sr-only">{t("loading")}</span>
            <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" aria-hidden="true" />
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {header}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => persist(scenes)}
            disabled={save.isPending}
            aria-label={t("save")}
            className="inline-flex items-center gap-1 px-2 py-1 rounded bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {save.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <Save className="w-3.5 h-3.5" aria-hidden="true" />
            )}
            {t("save")}
          </button>
          <span className="flex-1" />
          <button
            type="button"
            onClick={openFullPlanner}
            className="px-2 py-1 rounded border border-border text-xs font-medium hover:bg-accent"
          >
            {t("openFullPlanner")}
          </button>
        </div>

        {save.isError && (
          <p role="alert" className="text-xs text-destructive">
            {t("saveError")}
          </p>
        )}

        {scenes.length === 0 ? (
          <p className="text-xs text-muted-foreground py-2">{t("empty")}</p>
        ) : (
          <ul className="space-y-1.5">
            {scenes.map((scene, index) => (
              <SceneCard
                key={scene.id}
                scene={scene}
                index={index}
                total={scenes.length}
                novelId={novelId}
                chapterId={chapterId}
                onEdit={(next) => setScenes(scenes.map((s) => (s.id === next.id ? next : s)))}
                onMoveUp={() => move(index, -1)}
                onMoveDown={() => move(index, 1)}
                onRemove={() => persist(scenes.filter((_, i) => i !== index))}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
