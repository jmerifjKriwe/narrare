"use client";

import { Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import {
  ANALYSIS_TYPES,
  type AnalysisType,
  getDetailRows,
  getScore,
  getSuggestions,
  MOCK_STATS,
} from "./analysis-data";

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
            { value: MOCK_STATS.totalWords, label: t("analysis.totalWords") },
            { value: MOCK_STATS.chapters, label: t("analysis.chapters") },
            { value: MOCK_STATS.characters, label: t("analysis.characters") },
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
                              <div className="h-full bg-primary rounded-full transition-all" />
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
