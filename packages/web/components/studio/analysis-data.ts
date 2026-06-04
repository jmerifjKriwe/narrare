import { BookOpen, Clock, TrendingUp, Users } from "lucide-react";
import type { useTranslations } from "next-intl";

export type AnalysisType = "readability" | "pacing" | "characters" | "timeline";

interface AnalysisTypeConfig {
  id: AnalysisType;
  icon: typeof BookOpen;
  titleKey: string;
  descriptionKey: string;
}

export const ANALYSIS_TYPES: AnalysisTypeConfig[] = [
  {
    id: "readability",
    icon: BookOpen,
    titleKey: "analysis.readability.title",
    descriptionKey: "analysis.readability.description",
  },
  {
    id: "pacing",
    icon: TrendingUp,
    titleKey: "analysis.pacing.title",
    descriptionKey: "analysis.pacing.description",
  },
  {
    id: "characters",
    icon: Users,
    titleKey: "analysis.characterAnalysis.title",
    descriptionKey: "analysis.characterAnalysis.description",
  },
  {
    id: "timeline",
    icon: Clock,
    titleKey: "analysis.timeline.title",
    descriptionKey: "analysis.timeline.description",
  },
];

export const MOCK_STATS = {
  totalWords: 65,
  chapters: 2,
  characters: 2,
};

export const MOCK_RESULTS: Record<AnalysisType, Record<string, string | number>> = {
  readability: {
    score: 78,
    avgSentenceLength: 14.2,
    complexWords: 8,
    grade: "analysis.readability.grade",
  },
  pacing: {
    score: 65,
    actionScenes: 3,
    dialogueScenes: 5,
    descriptionScenes: 2,
  },
  characters: {
    mainCharacters: 2,
    annaAppearances: 2,
    steinAppearances: 1,
  },
  timeline: {
    score: 90,
    timespan: "3 Monate",
    inconsistencies: 0,
  },
};

export function getSuggestions(
  t: ReturnType<typeof useTranslations>,
  type: AnalysisType,
): string[] {
  switch (type) {
    case "readability":
      return [
        t("analysis.readability.suggestion1"),
        t("analysis.readability.suggestion2"),
        t("analysis.readability.suggestion3"),
      ];
    case "pacing":
      return [
        t("analysis.pacing.suggestion1"),
        t("analysis.pacing.suggestion2"),
        t("analysis.pacing.suggestion3"),
      ];
    case "characters":
      return [
        t("analysis.characterAnalysis.suggestion1"),
        t("analysis.characterAnalysis.suggestion2"),
      ];
    case "timeline":
      return [t("analysis.timeline.suggestion1"), t("analysis.timeline.suggestion2")];
  }
}

export function getDetailRows(
  t: ReturnType<typeof useTranslations>,
  type: AnalysisType,
): { label: string; value: string }[] {
  switch (type) {
    case "readability":
      return [
        {
          label: t("analysis.readability.grade"),
          value: t(String(MOCK_RESULTS.readability.grade)),
        },
        {
          label: t("analysis.readability.avgSentence"),
          value: String(MOCK_RESULTS.readability.avgSentenceLength),
        },
        {
          label: t("analysis.readability.complexWords"),
          value: `${MOCK_RESULTS.readability.complexWords}%`,
        },
      ];
    case "pacing":
      return [
        {
          label: t("analysis.pacing.actionScenes"),
          value: String(MOCK_RESULTS.pacing.actionScenes),
        },
        {
          label: t("analysis.pacing.dialogueScenes"),
          value: String(MOCK_RESULTS.pacing.dialogueScenes),
        },
        {
          label: t("analysis.pacing.descriptionScenes"),
          value: String(MOCK_RESULTS.pacing.descriptionScenes),
        },
      ];
    case "characters":
      return [
        {
          label: t("analysis.characterAnalysis.mainCharacters"),
          value: String(MOCK_RESULTS.characters.mainCharacters),
        },
        {
          label: `Anna — ${t("analysis.characterAnalysis.appearances")}`,
          value: String(MOCK_RESULTS.characters.annaAppearances),
        },
        {
          label: `Dr. Stein — ${t("analysis.characterAnalysis.appearances")}`,
          value: String(MOCK_RESULTS.characters.steinAppearances),
        },
      ];
    case "timeline":
      return [
        { label: t("analysis.timeline.timespan"), value: String(MOCK_RESULTS.timeline.timespan) },
        {
          label: t("analysis.timeline.inconsistencies"),
          value: String(MOCK_RESULTS.timeline.inconsistencies),
        },
      ];
  }
}

export function getScore(type: AnalysisType): number {
  const result = MOCK_RESULTS[type];
  if ("score" in result) {
    return result.score as number;
  }
  return 0;
}
