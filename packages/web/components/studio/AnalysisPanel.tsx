"use client";

import { BookOpen, Clock, Sparkles, TrendingUp, Users } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

type AnalysisType = "readability" | "pacing" | "characters" | "timeline";

interface AnalysisTypeConfig {
  id: AnalysisType;
  icon: typeof BookOpen;
  titleKey: string;
  descriptionKey: string;
}

const ANALYSIS_TYPES: AnalysisTypeConfig[] = [
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

const MOCK_STATS = {
  totalWords: 65,
  chapters: 2,
  characters: 2,
};

const MOCK_RESULTS: Record<AnalysisType, Record<string, string | number>> = {
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

function getSuggestions(t: ReturnType<typeof useTranslations>, type: AnalysisType): string[] {
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

function getDetailRows(
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
        {
          label: t("analysis.timeline.timespan"),
          value: String(MOCK_RESULTS.timeline.timespan),
        },
        {
          label: t("analysis.timeline.inconsistencies"),
          value: String(MOCK_RESULTS.timeline.inconsistencies),
        },
      ];
  }
}

interface AnalysisPanelProps {
  novelId: string;
}

export function AnalysisPanel({ novelId }: AnalysisPanelProps) {
  const t = useTranslations("studio");

  // novelId is available for future API calls to fetch novel-specific data
  void novelId;
  const [activeAnalysis, setActiveAnalysis] = useState<AnalysisType | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  function handleAnalyze(type: AnalysisType) {
    if (activeAnalysis === type) {
      setActiveAnalysis(null);
      return;
    }
    setActiveAnalysis(type);
    setIsAnalyzing(true);
    // Mock delay
    setTimeout(() => {
      setIsAnalyzing(false);
    }, 1500);
  }

  function getScore(type: AnalysisType): number {
    const result = MOCK_RESULTS[type];
    if ("score" in result) {
      return result.score as number;
    }
    return 0;
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-medium mb-2">{t("analysis.title")}</h1>
          <p className="text-muted-foreground">{t("analysis.description")}</p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            {
              value: MOCK_STATS.totalWords,
              label: t("analysis.totalWords"),
            },
            { value: MOCK_STATS.chapters, label: t("analysis.chapters") },
            {
              value: MOCK_STATS.characters,
              label: t("analysis.characters"),
            },
          ].map((stat) => (
            <div key={stat.label} className="bg-card border border-border rounded-lg p-6">
              <div className="text-3xl font-medium mb-1">{stat.value}</div>
              <div className="text-sm text-muted-foreground">{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Analysis cards */}
        <div className="space-y-4 mb-8">
          {ANALYSIS_TYPES.map((analysis) => {
            const Icon = analysis.icon;
            const isExpanded = activeAnalysis === analysis.id;
            const score = getScore(analysis.id);

            return (
              <div
                key={analysis.id}
                className="bg-card border border-border rounded-lg overflow-hidden"
              >
                {/* Card header */}
                <button
                  type="button"
                  onClick={() => handleAnalyze(analysis.id)}
                  className="w-full p-6 flex items-start gap-4 hover:bg-accent transition-colors text-left"
                >
                  <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
                    <Icon className="w-6 h-6" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="mb-1 font-medium">{t(analysis.titleKey)}</h3>
                    <p className="text-sm text-muted-foreground">{t(analysis.descriptionKey)}</p>
                  </div>
                  <div className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity flex-shrink-0 text-sm shadow-sm">
                    <Sparkles className="w-4 h-4" />
                    <span>{t("analysis.analyze")}</span>
                  </div>
                </button>

                {/* Results panel */}
                {isExpanded && (
                  <div className="border-t border-border p-6 bg-muted/20">
                    {isAnalyzing ? (
                      <div className="flex items-center justify-center py-8 text-muted-foreground">
                        <Sparkles className="w-5 h-5 animate-pulse mr-2" />
                        <span>{t("analysis.analyzing")}</span>
                      </div>
                    ) : (
                      <div>
                        {/* Score bar */}
                        {score > 0 && (
                          <div className="mb-6">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-sm font-medium">{t("analysis.score")}</span>
                              <span className="text-2xl font-medium">{score}</span>
                            </div>
                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                              <div
                                className="h-full bg-primary rounded-full transition-all"
                                style={{ width: `${score}%` }}
                              />
                            </div>
                          </div>
                        )}

                        {/* Detail rows */}
                        <div className="grid grid-cols-3 gap-4 mb-6">
                          {getDetailRows(t, analysis.id).map((row) => (
                            <div
                              key={`${analysis.id}-detail-${row.label}`}
                              className="bg-background rounded-lg p-3"
                            >
                              <div className="text-xs text-muted-foreground mb-1">{row.label}</div>
                              <div className="text-sm font-medium">{row.value}</div>
                            </div>
                          ))}
                        </div>

                        {/* Suggestions */}
                        <div>
                          <h4 className="text-sm font-medium mb-3">{t("analysis.insights")}</h4>
                          <ul className="space-y-2">
                            {getSuggestions(t, analysis.id).map((suggestion) => (
                              <li
                                key={`${analysis.id}-${suggestion.slice(0, 40)}`}
                                className="flex items-start gap-2 text-sm text-muted-foreground"
                              >
                                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-muted-foreground flex-shrink-0" />
                                <span>{suggestion}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
