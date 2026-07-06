/**
 * Generation form state + request builder extracted from
 * generationPanelController (RULE-04 / AUFG-03-04).
 *
 * Owns the user-editable config (mode, outline, prompt, word target,
 * tone) and the `buildRequest` helper that assembles a GenerateRequest
 * from the current config.
 */

import { type Dispatch, type SetStateAction, useCallback, useState } from "react";
import type { GenerateRequest, GenerationMode } from "@/lib/api/generation";

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
  buildRequest: () => GenerateRequest;
}

export function useGenerationConfig(): UseGenerationConfigResult {
  const [mode, setMode] = useState<GenerationMode>("full_draft");
  const [outline, setOutline] = useState("");
  const [prompt, setPrompt] = useState("");
  const [wordTarget, setWordTarget] = useState<number>(0);
  const [tone, setTone] = useState("balanced");

  const buildRequest = useCallback((): GenerateRequest => {
    const req: GenerateRequest = {
      mode,
      word_target: wordTarget > 0 ? wordTarget : null,
      tone,
    };
    if (mode === "full_draft" || mode === "scene_by_scene") req.outline = outline || null;
    if (mode === "full_draft" || mode === "interview_assisted") req.prompt = prompt || null;
    if (mode === "interview_assisted") req.auto_continue = true;
    return req;
  }, [mode, outline, prompt, wordTarget, tone]);

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
    buildRequest,
  };
}
