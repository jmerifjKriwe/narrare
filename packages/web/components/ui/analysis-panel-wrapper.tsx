"use client";

import { PhaseCrossfade } from "./phase-crossfade";

interface AnalysisPanelWrapperProps {
  readonly phase: string;
  readonly children: React.ReactNode;
}

/**
 * Shared wrapper for analysis panels (BetaReader, Consistency, POV, etc.).
 * Adds crossfade animation between idle/loading/results/error phases.
 */
export function AnalysisPanelWrapper({ phase, children }: AnalysisPanelWrapperProps) {
  return <PhaseCrossfade phase={phase}>{children}</PhaseCrossfade>;
}
