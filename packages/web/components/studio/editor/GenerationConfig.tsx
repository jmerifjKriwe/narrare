"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import type { Dispatch, SetStateAction } from "react";
import type { GenerationMode } from "@/lib/api/generation";
import { GenerationInputFields } from "./GenerationInputFields";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GenerationConfigProps {
  readonly mode: GenerationMode;
  readonly setMode: Dispatch<SetStateAction<GenerationMode>>;
  readonly outline: string;
  readonly setOutline: Dispatch<SetStateAction<string>>;
  readonly prompt: string;
  readonly setPrompt: Dispatch<SetStateAction<string>>;
  readonly wordTarget: number;
  readonly setWordTarget: Dispatch<SetStateAction<number>>;
  readonly tone: string;
  readonly setTone: Dispatch<SetStateAction<string>>;
  readonly isPending: boolean;
  readonly onGenerate: () => void;
  readonly onStartSession?: (mode: string) => void;
}

const MODE_TABS: { value: GenerationMode; labelKey: string }[] = [
  { value: "full_draft", labelKey: "generationPanel.modeFullDraft" },
  { value: "scene_by_scene", labelKey: "generationPanel.modeSceneByScene" },
  { value: "interview_assisted", labelKey: "generationPanel.modeInterview" },
  { value: "interactive_session", labelKey: "generationPanel.modeInteractive" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GenerationConfig({
  mode,
  setMode,
  outline,
  setOutline,
  prompt,
  setPrompt,
  wordTarget,
  setWordTarget,
  tone,
  setTone,
  isPending,
  onGenerate,
  onStartSession,
}: GenerationConfigProps) {
  const t = useTranslations("studio");

  const showInput =
    mode === "full_draft" || mode === "scene_by_scene" || mode === "interview_assisted";
  const isInteractive = mode === "interactive_session";
  const isSessionMode = mode === "interactive_session" || mode === "interview_assisted";

  return (
    <>
      <div className="flex flex-wrap gap-1.5">
        {MODE_TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => setMode(tab.value)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              mode === tab.value
                ? "bg-primary text-primary-foreground"
                : "bg-accent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t(tab.labelKey)}
          </button>
        ))}
      </div>

      {showInput && (
        <GenerationInputFields
          mode={mode}
          outline={outline}
          setOutline={setOutline}
          prompt={prompt}
          setPrompt={setPrompt}
          wordTarget={wordTarget}
          setWordTarget={setWordTarget}
          tone={tone}
          setTone={setTone}
        />
      )}

      {isInteractive && (
        <p className="text-sm text-muted-foreground">
          {t("generationPanel.interactiveDescription")}
        </p>
      )}

      {mode === "interview_assisted" && (
        <p className="text-sm text-muted-foreground">{t("generationPanel.interviewDescription")}</p>
      )}

      <button
        type="button"
        onClick={isSessionMode ? () => onStartSession?.(mode) : onGenerate}
        disabled={isPending}
        className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isPending ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Sparkles className="w-4 h-4" />
        )}
        <span>
          {isPending
            ? t("generationPanel.starting")
            : isSessionMode
              ? t("generationPanel.startSession")
              : t("generationPanel.generate")}
        </span>
      </button>
    </>
  );
}
