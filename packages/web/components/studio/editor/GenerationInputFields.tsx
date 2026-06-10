"use client";

import { useTranslations } from "next-intl";
import type { Dispatch, SetStateAction } from "react";
import type { GenerationMode } from "@/lib/api/generation";
import { BUNDLED_TONES } from "@/lib/constants/tones";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GenerationInputFieldsProps {
  readonly mode: GenerationMode;
  readonly outline: string;
  readonly setOutline: Dispatch<SetStateAction<string>>;
  readonly prompt: string;
  readonly setPrompt: Dispatch<SetStateAction<string>>;
  readonly wordTarget: number;
  readonly setWordTarget: Dispatch<SetStateAction<number>>;
  readonly tone: string;
  readonly setTone: Dispatch<SetStateAction<string>>;
  readonly onGenerate?: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Mode-specific input fields for generation configuration. */
export function GenerationInputFields({
  mode,
  outline,
  setOutline,
  prompt,
  setPrompt,
  wordTarget,
  setWordTarget,
  tone,
  setTone,
  onGenerate,
}: GenerationInputFieldsProps) {
  const t = useTranslations("studio");

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>, action: () => void) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      action();
    }
  };

  return (
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
            onKeyDown={(e) => onGenerate && handleKeyDown(e, onGenerate)}
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
            onKeyDown={(e) => onGenerate && handleKeyDown(e, onGenerate)}
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
            {BUNDLED_TONES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {t(opt.label)}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
