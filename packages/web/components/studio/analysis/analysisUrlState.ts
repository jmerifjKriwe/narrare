import { ANALYSIS_TYPES, type AnalysisType } from "../analysis-data";

const ANALYSIS_IDS = new Set<AnalysisType>(ANALYSIS_TYPES.map((analysis) => analysis.id));

export function parseAnalysisPanelParam(value: string | null): AnalysisType | null {
  if (value !== null && ANALYSIS_IDS.has(value as AnalysisType)) return value as AnalysisType;
  return null;
}

export function serializeAnalysisPanelParam(panel: AnalysisType | null): string | null {
  return panel;
}
