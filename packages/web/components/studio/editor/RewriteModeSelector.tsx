"use client";

import { Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { RewriteMode } from "@/lib/api/generation";
import { RewriteFooter } from "./RewriteFooter";
import { RewriteModeOptions } from "./RewriteModeOptions";

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

const TONE_OPTIONS = ["more dramatic"] as const;
const STYLE_OPTIONS = ["simplify"] as const;
const FIX_OPTIONS = ["show don't tell"] as const;

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

        <RewriteModeOptions
          mode={mode}
          option={option}
          setOption={setOption}
          voiceCharacter={voiceCharacter}
          setVoiceCharacter={setVoiceCharacter}
          customInstructions={customInstructions}
          setCustomInstructions={setCustomInstructions}
        />

        <RewriteFooter
          mode={mode}
          customInstructions={customInstructions}
          count={count}
          setCount={setCount}
          isGenerating={isGenerating}
          onGenerate={handleGenerate}
          onCancel={onCancel}
        />
      </div>
    </div>
  );
}
