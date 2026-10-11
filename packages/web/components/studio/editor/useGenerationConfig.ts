/**
 * Generation form state + request builder extracted from
 * generationPanelController (RULE-04 / AUFG-03-04).
 *
 * Owns the user-editable config (mode, outline, prompt, word target,
 * tone, scene-plan usage) and the `buildRequest` helper that assembles a
 * GenerateRequest from the current config.
 */

import { type Dispatch, type SetStateAction, useCallback, useState } from "react";
import type { GenerateRequest, GenerateScene, GenerationMode } from "@/lib/api/generation";
import type { ScenePlan } from "@/types/planning";

interface UseGenerationConfigOptions {
  /**
   * The current chapter's scene plans, injected by GenerationPanel from
   * `useScenePlans(novelId, chapterId)` (PLAN-001 spec §8.1).
   */
  readonly scenePlans?: ScenePlan[] | null;
}

interface UseGenerationConfigResult {
  mode: GenerationMode;
  outline: string;
  prompt: string;
  wordTarget: number;
  tone: string;
  setMode: Dispatch<SetStateAction<GenerationMode>>;
  setOutline: Dispatch<SetStateAction<string>>;
  setPrompt: Dispatch<SetStateAction<string>>;
  setWordTarget: Dispatch<SetStateAction<number>>;
  setTone: Dispatch<SetStateAction<string>>;
  /**
   * Effective "write from scene plans": default ON while the chapter has
   * plans, unless the user explicitly toggled off (session-scoped).
   */
  useScenePlans: boolean;
  setUseScenePlans: Dispatch<SetStateAction<boolean>>;
  buildRequest: () => GenerateRequest;
}

const SCENE_PLANS_PREF_KEY = "studio.generation.useScenePlans";

/**
 * Explicit "use scene plans" preference, persisted in sessionStorage (spec
 * §8.1: default ON when plans exist; an explicit toggle-off persists for the
 * session — surviving GenerationPanel unmounts when another right panel is
 * opened, and tab reloads). `null` = untouched → default ON. Best-effort
 * write like content recovery: an unavailable store never blocks generating.
 */
function readScenePlansPreference(): boolean | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(SCENE_PLANS_PREF_KEY);
  return raw === null ? null : raw === "1";
}

function writeScenePlansPreference(value: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(SCENE_PLANS_PREF_KEY, value ? "1" : "0");
  } catch {
    // sessionStorage full or unavailable — preference stays in-memory only.
  }
}

/**
 * Map a persisted scene plan to the request-scene shape — field-exact mirror
 * of `GenerateSceneSchema` (apps/api/narrare/writing/schemas_scenes.py,
 * RULE-17): the writer needs identity-free names, not KB linkage or ids.
 */
function toGenerateScene(scene: ScenePlan): GenerateScene {
  return {
    title: scene.title,
    pov_character_name: scene.pov_character_ref?.name ?? "",
    location_name: scene.location_ref?.name ?? "",
    present_characters: scene.present_characters.map(({ name, goal }) => ({ name, goal })),
    purpose: scene.purpose,
    conflict: scene.conflict,
    resolution: scene.resolution,
    beats: [...scene.beats],
    status: scene.status,
  };
}

export function useGenerationConfig(
  options: UseGenerationConfigOptions = {},
): UseGenerationConfigResult {
  const { scenePlans = null } = options;
  const [mode, setMode] = useState<GenerationMode>("full_draft");
  const [outline, setOutline] = useState("");
  const [prompt, setPrompt] = useState("");
  const [wordTarget, setWordTarget] = useState<number>(0);
  const [tone, setTone] = useState("balanced");
  const [explicitPreference, setExplicitPreference] = useState<boolean | null>(
    readScenePlansPreference,
  );

  const hasScenePlans = scenePlans !== null && scenePlans.length > 0;
  const useScenePlans = (explicitPreference ?? true) && hasScenePlans;

  const setUseScenePlans = useCallback<Dispatch<SetStateAction<boolean>>>(
    (value) => {
      // Resolve + persist OUTSIDE the state updater: updaters must stay pure
      // (React may double-invoke them, e.g. StrictMode) — side effects belong
      // in the handler. Idempotent write, same resolved value as before.
      const next = typeof value === "function" ? value(explicitPreference ?? true) : value;
      writeScenePlansPreference(next);
      setExplicitPreference(next);
    },
    [explicitPreference],
  );

  const buildRequest = useCallback((): GenerateRequest => {
    const req: GenerateRequest = {
      mode,
      word_target: wordTarget > 0 ? wordTarget : null,
      tone,
    };
    if (mode === "full_draft" || mode === "scene_by_scene") req.outline = outline || null;
    if (mode === "full_draft" || mode === "interview_assisted") req.prompt = prompt || null;
    if (mode === "interview_assisted") req.auto_continue = true;
    if (mode === "scene_by_scene" && useScenePlans && scenePlans && scenePlans.length > 0) {
      req.scenes = scenePlans.map(toGenerateScene);
    }
    return req;
  }, [mode, outline, prompt, wordTarget, tone, useScenePlans, scenePlans]);

  return {
    mode,
    outline,
    prompt,
    wordTarget,
    tone,
    setMode,
    setOutline,
    setPrompt,
    setWordTarget,
    setTone,
    useScenePlans,
    setUseScenePlans,
    buildRequest,
  };
}
