"use client";

import { useTranslations } from "next-intl";
import type { RewriteMode } from "@/lib/api/generation";

// ---------------------------------------------------------------------------
// Mode options
// ---------------------------------------------------------------------------

const TONE_OPTIONS = [
  "more dramatic",
  "more subdued",
  "more humorous",
  "more tense",
  "more formal",
  "more casual",
] as const;

const STYLE_OPTIONS = [
  "simplify",
  "elaborate",
  "more active",
  "more descriptive",
  "varied sentences",
] as const;

const FIX_OPTIONS = [
  "show don't tell",
  "remove redundancies",
  "strengthen verbs",
  "fix phrasing",
] as const;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RewriteModeOptionsProps {
  readonly mode: RewriteMode;
  readonly option: string;
  readonly setOption: (option: string) => void;
  readonly voiceCharacter: string;
  readonly setVoiceCharacter: (value: string) => void;
  readonly customInstructions: string;
  readonly setCustomInstructions: (value: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Mode-specific option controls for the rewrite modal. */
export function RewriteModeOptions({
  mode,
  option,
  setOption,
  voiceCharacter,
  setVoiceCharacter,
  customInstructions,
  setCustomInstructions,
}: RewriteModeOptionsProps) {
  const t = useTranslations("studio");

  return (
    <div className="p-5 border-b border-border">
      {mode === "tone" && (
        <div>
          <label htmlFor="tone-option" className="block text-sm font-medium mb-2">
            {t("rewrite.toneOption")}
          </label>
          <select
            id="tone-option"
            value={option}
            onChange={(e) => setOption(e.target.value)}
            className="w-full px-3 py-2 bg-input-background border border-border rounded-lg text-sm"
          >
            {TONE_OPTIONS.map((o) => (
              <option key={o} value={o}>
                {t(`rewrite.toneOptions.${o.replace(/\s+/g, "")}`)}
              </option>
            ))}
          </select>
        </div>
      )}

      {mode === "style" && (
        <div>
          <label htmlFor="style-option" className="block text-sm font-medium mb-2">
            {t("rewrite.styleOption")}
          </label>
          <select
            id="style-option"
            value={option}
            onChange={(e) => setOption(e.target.value)}
            className="w-full px-3 py-2 bg-input-background border border-border rounded-lg text-sm"
          >
            {STYLE_OPTIONS.map((o) => (
              <option key={o} value={o}>
                {t(`rewrite.styleOptions.${o.replace(/\s+/g, "")}`)}
              </option>
            ))}
          </select>
        </div>
      )}

      {mode === "voice" && (
        <div>
          <label htmlFor="voice-character" className="block text-sm font-medium mb-2">
            {t("rewrite.voiceCharacter")}
          </label>
          <input
            id="voice-character"
            type="text"
            value={voiceCharacter}
            onChange={(e) => setVoiceCharacter(e.target.value)}
            placeholder={t("rewrite.voiceCharacterPlaceholder")}
            className="w-full px-3 py-2 bg-input-background border border-border rounded-lg text-sm"
          />
        </div>
      )}

      {mode === "fix" && (
        <div>
          <label htmlFor="fix-option" className="block text-sm font-medium mb-2">
            {t("rewrite.fixOption")}
          </label>
          <select
            id="fix-option"
            value={option}
            onChange={(e) => setOption(e.target.value)}
            className="w-full px-3 py-2 bg-input-background border border-border rounded-lg text-sm"
          >
            {FIX_OPTIONS.map((o) => (
              <option key={o} value={o}>
                {t(`rewrite.fixOptions.${o.replace(/\s+/g, "")}`)}
              </option>
            ))}
          </select>
        </div>
      )}

      {mode === "custom" && (
        <div>
          <label htmlFor="custom-instructions" className="block text-sm font-medium mb-2">
            {t("rewrite.customInstructions")}
          </label>
          <textarea
            id="custom-instructions"
            value={customInstructions}
            onChange={(e) => setCustomInstructions(e.target.value.slice(0, 500))}
            placeholder={t("rewrite.customInstructionsPlaceholder")}
            className="w-full px-3 py-2 bg-input-background border border-border rounded-lg text-sm"
            rows={3}
            maxLength={500}
          />
          <p className="mt-1 text-xs text-muted-foreground">{customInstructions.length}/500</p>
        </div>
      )}
    </div>
  );
}
