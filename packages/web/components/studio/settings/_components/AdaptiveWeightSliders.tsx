"use client";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import { Slider } from "@/components/ui/slider";
import type { AdaptiveWeightsInput } from "@/types";

const WEIGHTS = [
  { key: "preference", labelKey: "preference" },
  { key: "voice_fidelity", labelKey: "voice_fidelity" },
  { key: "style_constraints", labelKey: "style_constraints" },
  { key: "avoidance", labelKey: "avoidance" },
] as const satisfies readonly { key: keyof AdaptiveWeightsInput; labelKey: string }[];

export function AdaptiveWeightSliders({
  weights,
  onCommit,
  pending,
}: {
  weights: AdaptiveWeightsInput;
  onCommit: (next: AdaptiveWeightsInput) => void;
  pending: boolean;
}) {
  const t = useTranslations("adaptive");
  const [draft, setDraft] = useState<AdaptiveWeightsInput>(weights);

  // Keep local draft in sync when the server state changes (Decision 15 invalidation).
  if (
    draft.preference !== weights.preference ||
    draft.voice_fidelity !== weights.voice_fidelity ||
    draft.style_constraints !== weights.style_constraints ||
    draft.avoidance !== weights.avoidance
  ) {
    // Only re-sync when not actively pending (avoids clobbering an in-flight edit).
    if (!pending) setDraft(weights);
  }

  const handleCommit = useCallback(
    (key: keyof AdaptiveWeightsInput, value: number) => {
      const next = { ...draft, [key]: value } as AdaptiveWeightsInput;
      setDraft(next);
      onCommit(next);
    },
    [draft, onCommit],
  );

  return (
    <div className="space-y-4">
      <p className="font-medium">{t("weightsTitle")}</p>
      {WEIGHTS.map(({ key, labelKey }) => (
        <div key={key}>
          <div className="flex items-center justify-between text-sm">
            <label htmlFor={`weight-${key}`}>{t(`weight.${labelKey}`)}</label>
            <span className="text-muted-foreground tabular-nums">
              {Math.round((draft[key] ?? 0) * 100)}%
            </span>
          </div>
          <Slider
            id={`weight-${key}`}
            value={[draft[key] ?? 0]}
            min={0}
            max={1}
            step={0.01}
            disabled={pending}
            onValueChange={(v) => handleCommit(key, v[0] ?? 0)}
            aria-label={t(`weight.${labelKey}`)}
          />
        </div>
      ))}
    </div>
  );
}
