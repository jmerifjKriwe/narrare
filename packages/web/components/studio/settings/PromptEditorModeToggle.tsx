"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { PromptEditorMode } from "./usePromptEditorMode";

// --- Types ---

interface PromptEditorModeToggleProps {
  readonly mode: PromptEditorMode;
  readonly onChange: (mode: PromptEditorMode) => void;
}

const MODES: readonly PromptEditorMode[] = ["simple", "expert"];

// --- Component ---

/**
 * PromptEditorModeToggle — segmented "Einfach" | "Experte" control with a
 * contextual helper hint shown in simple mode.
 *
 * Presentation-only: receives the active ``mode`` and reports changes via
 * ``onChange``. The persistence/state lives in :func:`usePromptEditorMode`.
 * Each button exposes its label as an accessible name plus ``aria-pressed``
 * so screen readers announce the active segment.
 */
export function PromptEditorModeToggle({ mode, onChange }: PromptEditorModeToggleProps) {
  const t = useTranslations("studio");

  return (
    <div className="mb-4 flex flex-wrap items-center gap-3">
      <div className="inline-flex items-center gap-0.5 rounded-md border border-border bg-muted/30 p-0.5">
        {MODES.map((m) => {
          const isActive = m === mode;
          return (
            <button
              key={m}
              type="button"
              aria-pressed={isActive}
              onClick={() => onChange(m)}
              className={cn(
                "rounded px-3 py-1 text-xs font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              {t(m === "simple" ? "settings.prompts.modeSimple" : "settings.prompts.modeExpert")}
            </button>
          );
        })}
      </div>
      {mode === "simple" && (
        <span className="text-xs text-muted-foreground">
          {t("settings.prompts.modeSimpleHint")}
        </span>
      )}
    </div>
  );
}
