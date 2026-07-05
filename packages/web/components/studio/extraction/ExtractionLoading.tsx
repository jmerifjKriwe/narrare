"use client";

/**
 * ExtractionLoading — Loading state shown while the extraction agent
 * analyzes the chapter text.
 *
 * Shows phased progress (Analysing → Extracting → Finalizing) with
 * animated progress bar. The accessible `role="status"` / polite live
 * region, `aria-busy`, and loading spinner are provided by the
 * `StatusMessage` primitive (§16.3). The cancel control (when present)
 * is passed as the live region's actionable `action`.
 */

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { StatusMessage } from "@/components/ui/status-message";

const PHASES = ["analysing", "extracting", "finalizing"] as const;
type ProgressPhase = (typeof PHASES)[number];

const PHASE_DURATIONS: Record<ProgressPhase, number> = {
  analysing: 4000,
  extracting: 8000,
  finalizing: Number.POSITIVE_INFINITY,
};

interface ExtractionLoadingProps {
  readonly onCancel?: () => void;
}

export function ExtractionLoading({ onCancel }: ExtractionLoadingProps) {
  const t = useTranslations("studio");
  const tAction = useTranslations("studio.aiActions");
  const [phaseIndex, setPhaseIndex] = useState(0);

  const phase = PHASES[phaseIndex];

  useEffect(() => {
    if (phaseIndex >= PHASES.length - 1) return;
    const duration = PHASE_DURATIONS[PHASES[phaseIndex]];
    const timer = setTimeout(
      () => setPhaseIndex((i) => Math.min(i + 1, PHASES.length - 1)),
      duration,
    );
    return () => clearTimeout(timer);
  }, [phaseIndex]);

  const progressWidth = phase === "analysing" ? "35%" : phase === "extracting" ? "65%" : "90%";

  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <StatusMessage
        state="loading"
        message={tAction("aiThinking")}
        action={
          onCancel ? (
            <button type="button" onClick={onCancel} aria-label={tAction("stop")}>
              {tAction("stop")}
            </button>
          ) : undefined
        }
      />
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        {t(`kb.extractionPhase.${phase}`)}
      </p>
      <div className="mt-6 h-1.5 w-64 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-purple-500 transition-all duration-1000 ease-out"
          style={{ width: progressWidth }}
        />
      </div>
    </div>
  );
}
