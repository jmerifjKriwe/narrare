"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import type { Dispatch, SetStateAction } from "react";
import type { GenerationMode } from "@/lib/api/generation";

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

const TONE_OPTIONS = [
  { value: "balanced", labelKey: "generationPanel.toneBalanced" },
  { value: "dramatic", labelKey: "generationPanel.toneDramatic" },
  { value: "humorous", labelKey: "generationPanel.toneHumorous" },
  { value: "suspenseful", labelKey: "generationPanel.toneSuspenseful" },
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
      {/* Mode tabs */}
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

      {/* Mode-specific inputs */}
      {showInput && (
        <div className="flex flex-col gap-3">
          {(mode === "full_draft" || mode === "scene_by_scene") && (
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="gen-outline"
                className="text-[0.75rem] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                {t("generationPanel.outline")}
              </label>
              <textarea
                id="gen-outline"
                value={outline}
                onChange={(e) => setOutline(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-border rounded-lg bg-background text-foreground text-sm resize-none outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
                placeholder={t("generationPanel.outlinePlaceholder")}
              />
              {mode === "scene_by_scene" && (
                <p className="text-xs text-muted-foreground mt-1">
                  {t("generationPanel.outlineHelpScene")}
                </p>
              )}
            </div>
          )}

          {mode === "full_draft" && (
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="gen-prompt"
                className="text-[0.75rem] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                {t("generationPanel.prompt")}
              </label>
              <textarea
                id="gen-prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 border border-border rounded-lg bg-background text-foreground text-sm resize-none outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
                placeholder={t("generationPanel.promptPlaceholder")}
              />
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="gen-target"
                className="text-[0.75rem] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                {t("generationPanel.wordTarget")}
              </label>
              <input
                id="gen-target"
                type="number"
                min={0}
                value={wordTarget || ""}
                onChange={(e) => setWordTarget(Math.max(0, Number(e.target.value)))}
                className="w-full px-3 py-2 border border-border rounded-lg bg-background text-foreground text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
                placeholder="3000"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="gen-tone"
                className="text-[0.75rem] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                {t("generationPanel.tone")}
              </label>
              <select
                id="gen-tone"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-lg bg-background text-foreground text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
              >
                {TONE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {t(opt.labelKey)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {isInteractive && (
        <p className="text-sm text-muted-foreground">
          {t("generationPanel.interactiveDescription")}
        </p>
      )}

      {mode === "interview_assisted" && (
        <p className="text-sm text-muted-foreground">{t("generationPanel.interviewDescription")}</p>
      )}

      {/* Generate / Start Session button */}
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
