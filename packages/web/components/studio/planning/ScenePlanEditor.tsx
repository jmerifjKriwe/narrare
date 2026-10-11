"use client";

import { Loader2, Plus, Save, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { useDraftScenes, useSaveScenePlans, useScenePlans } from "@/lib/hooks/usePlanning";
import type { ScenePlan, SceneProposal } from "@/types/planning";
import { SceneCard } from "./SceneCard";

interface ScenePlanEditorProps {
  novelId: string;
  chapterId: string | null;
}

/** Renumber positions 1..N in list order (server diff-syncs by id). */
function withPositions(scenes: ScenePlan[]): ScenePlan[] {
  return scenes.map((scene, index) =>
    scene.position === index + 1 ? scene : { ...scene, position: index + 1 },
  );
}

const nowIso = () => new Date().toISOString();

/** Turn an AI proposal into a persisted-shape scene appended to the chapter. */
function proposalToScene(proposal: SceneProposal, position: number): ScenePlan {
  return {
    ...proposal,
    id: crypto.randomUUID(),
    position,
    status: "planned",
    created_at: nowIso(),
    updated_at: nowIso(),
  };
}

/** Inline error line (role="alert"); `subtle` renders the graceful AI notice. */
function ErrorLine({ children, subtle }: { children: React.ReactNode; subtle?: boolean }) {
  return (
    <p role="alert" className={`text-xs ${subtle ? "text-muted-foreground" : "text-destructive"}`}>
      {children}
    </p>
  );
}

/** Planning-tab scene editor: owns the local aggregate, saves structurally, and
 * orchestrates the AI draft generator. Field edits stay LOCAL until the user
 * saves (SceneForm → SceneCard → onEdit patch the local state only). */
export function ScenePlanEditor({ novelId, chapterId }: ScenePlanEditorProps) {
  const t = useTranslations("studio.planning.scenes");
  const { data: aggregate, isLoading } = useScenePlans(novelId, chapterId);
  const save = useSaveScenePlans(novelId);
  const draft = useDraftScenes(novelId);
  const draftEmpty = draft.data?.ai_unavailable || draft.data?.proposals.length === 0;

  const [scenes, setScenes] = useState<ScenePlan[]>([]);
  // Mirror for async callbacks (stale-closure-safe draft apply).
  const scenesRef = useRef<ScenePlan[]>([]);

  // The server aggregate is the source of truth after every fetch/invalidation.
  useEffect(() => {
    if (aggregate) setScenes(aggregate.scenes);
  }, [aggregate]);

  useEffect(() => {
    scenesRef.current = scenes;
  }, [scenes]);

  if (!chapterId) {
    return <p className="text-xs text-muted-foreground p-4">{t("noChapter")}</p>;
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" aria-label={t("loading")} />
      </div>
    );
  }

  const cid = chapterId; // narrowed: TS can't carry the guard into hoisted closures

  function persist(next: ScenePlan[]) {
    setScenes(next);
    save.mutate({ chapterId: cid, data: { scenes: withPositions(next) } });
  }

  function handleAdd() {
    persist([
      ...scenes,
      {
        id: crypto.randomUUID(),
        position: scenes.length + 1,
        title: "",
        pov_character_ref: null,
        location_ref: null,
        present_characters: [],
        purpose: "",
        conflict: "",
        resolution: "",
        beats: [],
        status: "planned",
        created_at: nowIso(),
        updated_at: nowIso(),
      },
    ]);
  }

  function handleMove(index: number, dir: -1 | 1) {
    const next = [...scenes];
    const target = index + dir;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    persist(next);
  }

  function handleRemove(index: number) {
    persist(scenes.filter((_, i) => i !== index));
  }

  function handleDraft() {
    draft.mutate(
      { chapterId: cid, body: {} },
      {
        onSuccess: (res) => {
          if (res.ai_unavailable || res.proposals.length === 0) return;
          const current = scenesRef.current;
          const appended = res.proposals.map((p, i) => proposalToScene(p, current.length + i + 1));
          persist([...current, ...appended]);
        },
      },
    );
  }

  return (
    <div className="p-3 space-y-2">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleAdd}
          className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs font-medium hover:bg-accent"
        >
          <Plus className="w-3.5 h-3.5" aria-hidden="true" /> {t("addScene")}
        </button>
        <button
          type="button"
          onClick={handleDraft}
          disabled={draft.isPending}
          className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs font-medium hover:bg-accent disabled:opacity-50"
        >
          {draft.isPending ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />
          )}
          {t("draftWithAi")}
        </button>
        <span className="flex-1" />
        <button
          type="button"
          onClick={() => save.mutate({ chapterId: cid, data: { scenes: withPositions(scenes) } })}
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
      </div>

      {save.isError && <ErrorLine>{t("saveError")}</ErrorLine>}
      {draft.isError && <ErrorLine>{t("aiUnavailable")}</ErrorLine>}
      {draftEmpty && <ErrorLine subtle>{t("aiUnavailable")}</ErrorLine>}

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
              onMoveUp={() => handleMove(index, -1)}
              onMoveDown={() => handleMove(index, 1)}
              onRemove={() => handleRemove(index)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
