"use client";

/**
 * AnalysisLoading — Loading state for worldbuilding analysis with phased progress.
 *
 * Shows animated spinner with phase-based progress estimation and cancel.
 * Uses studio.aiActions.aiThinking label (§16.3).
 */

import { Loader2, StopCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

const PHASES = ["analysing", "detecting", "finalizing"] as const;
const PHASE_DURATIONS = [4000, 8000, Number.POSITIVE_INFINITY];

interface AnalysisLoadingProps {
  readonly onCancel?: () => void;
}

export function AnalysisLoading({ onCancel }: AnalysisLoadingProps) {
  const tAction = useTranslations("studio.aiActions");
  const t = useTranslations("studio");
  const [phaseIndex, setPhaseIndex] = useState(0);

  useEffect(() => {
    if (phaseIndex >= PHASES.length - 1) return;
    const timer = setTimeout(
      () => setPhaseIndex((i) => Math.min(i + 1, PHASES.length - 1)),
      PHASE_DURATIONS[phaseIndex],
    );
    return () => clearTimeout(timer);
  }, [phaseIndex]);

  const phase = PHASES[phaseIndex];
  const progressWidth = phase === "analysing" ? "30%" : phase === "detecting" ? "65%" : "90%";

  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="relative mb-6">
        <div className="w-16 h-16 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
        </div>
      </div>
      <p className="text-lg font-medium mb-2">{tAction("aiThinking")}</p>
      <p className="text-sm text-muted-foreground">{t("worldbuilding.analyzing")}</p>
      <div className="w-64 h-1.5 bg-muted rounded-full overflow-hidden mt-6">
        <div
          className="h-full bg-purple-500 rounded-full transition-all duration-1000 ease-out"
          style={{ width: progressWidth }}
        />
      </div>
      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="mt-6 flex items-center gap-1.5 px-4 py-2 text-sm text-muted-foreground hover:text-foreground border border-border rounded-md hover:bg-muted transition-colors"
        >
          <StopCircle className="w-4 h-4" />
          {tAction("stop")}
        </button>
      )}
    </div>
  );
}
