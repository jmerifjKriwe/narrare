"use client";

import { Loader2, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { RewriteMode } from "@/lib/api/generation";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RewriteModeSelectorProps {
  readonly selectionLength: number;
  readonly onGenerate: (config: RewriteConfig) => void;
  readonly onCancel: () => void;
}

export interface RewriteConfig {
  mode: RewriteMode;
  option: string;
  count: number;
  customInstructions?: string;
}

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

const MODES: { value: RewriteMode; labelKey: string }[] = [
  { value: "tone", labelKey: "rewrite.modeTone" },
  { value: "style", labelKey: "rewrite.modeStyle" },
  { value: "voice", labelKey: "rewrite.modeVoice" },
  { value: "fix", labelKey: "rewrite.modeFix" },
  { value: "custom", labelKey: "rewrite.modeCustom" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RewriteModeSelector({
  selectionLength: _selectionLength,
  onGenerate,
  onCancel,
}: RewriteModeSelectorProps) {
  const t = useTranslations("studio");
  const [mode, setMode] = useState<RewriteMode>("tone");
  const [option, setOption] = useState<string>(TONE_OPTIONS[0]);
  const [count, setCount] = useState(1);
  const [customInstructions, setCustomInstructions] = useState("");
  const [voiceCharacter, setVoiceCharacter] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerate = () => {
    setIsGenerating(true);
    const config: RewriteConfig = {
      mode,
      option: mode === "custom" ? "custom" : option,
      count,
      customInstructions: mode === "custom" ? customInstructions : undefined,
    };
    if (mode === "voice") {
      config.option = voiceCharacter;
    }
    onGenerate(config);
  };

  const handleModeChange = (newMode: RewriteMode) => {
    setMode(newMode);
    if (newMode === "tone") setOption(TONE_OPTIONS[0]);
    else if (newMode === "style") setOption(STYLE_OPTIONS[0]);
    else if (newMode === "fix") setOption(FIX_OPTIONS[0]);
    else if (newMode === "voice") setVoiceCharacter("");
    else if (newMode === "custom") setCustomInstructions("");
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card border border-border rounded-xl shadow-2xl max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary" />
            <h3 className="font-medium">{t("rewrite.title")}</h3>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="p-1 rounded-md hover:bg-accent transition-colors"
            aria-label={t("aiActions.stop")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Mode buttons */}
        <div className="p-5 border-b border-border">
          <div className="flex gap-2">
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                onClick={() => handleModeChange(m.value)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md border transition-colors ${
                  mode === m.value
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border hover:border-primary/50"
                }`}
              >
                {t(m.labelKey)}
              </button>
            ))}
          </div>
        </div>

        {/* Mode-specific options */}
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

        {/* Count selector + actions */}
        <div className="p-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium">{t("rewrite.count")}</span>
            <div className="flex gap-1">
              {[1, 2, 3].map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCount(c)}
                  className={`w-8 h-8 text-xs font-medium rounded-md border transition-colors ${
                    count === c
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border hover:border-primary/50"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-sm border border-border rounded-lg hover:bg-accent transition-colors"
            >
              {t("aiActions.stop")}
            </button>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={
                isGenerating || (mode === "custom" && customInstructions.trim().length === 0)
              }
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{t("rewrite.generating")}</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>{t("rewrite.generate")}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
