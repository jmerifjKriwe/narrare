"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  TrendingUp,
  Users,
  Clock,
  Sparkles,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { chaptersApi } from "@/lib/api/client";
import { formatWordCount } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AnalysisViewProps {
  novelId: string;
}

// ---------------------------------------------------------------------------
// Analysis tools configuration
// ---------------------------------------------------------------------------

interface AnalysisToolConfig {
  id: string;
  icon: React.ComponentType<{ className?: string }>;
  titleKey: string;
  descriptionKey: string;
}

const ANALYSIS_TOOLS: AnalysisToolConfig[] = [
  {
    id: "readability",
    icon: BookOpen,
    titleKey: "readability",
    descriptionKey: "readabilityDescription",
  },
  {
    id: "pacing",
    icon: TrendingUp,
    titleKey: "pacing",
    descriptionKey: "pacingDescription",
  },
  {
    id: "characters",
    icon: Users,
    titleKey: "characterAnalysis",
    descriptionKey: "characterAnalysisDescription",
  },
  {
    id: "timeline",
    icon: Clock,
    titleKey: "timeline",
    descriptionKey: "timelineDescription",
  },
];

// ---------------------------------------------------------------------------
// AnalysisView — statistics cards + analysis tool stubs
// ---------------------------------------------------------------------------

export function AnalysisView({ novelId }: AnalysisViewProps) {
  const t = useTranslations("editor");

  // Fetch chapters to compute word count and chapter count
  const { data: chapters = [] } = useQuery({
    queryKey: ["chapters", novelId],
    queryFn: () => chaptersApi.list(novelId),
  });

  const totalWords = chapters.reduce((sum, ch) => sum + ch.word_count, 0);
  const chapterCount = chapters.length;
  // Characters count — 0 until KB module exists
  const characterCount = 0;

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <h2 className="text-2xl font-semibold text-foreground mb-2">
          {t("analysisTitle")}
        </h2>
        <p className="text-muted-foreground mb-8">
          {t("analysisDescription")}
        </p>

        {/* Statistics cards */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <StatCard value={formatWordCount(totalWords)} label={t("totalWords")} />
          <StatCard value={String(chapterCount)} label={t("chaptersCount")} />
          <StatCard value={String(characterCount)} label={t("wb_characters")} />
        </div>

        {/* Analysis tools */}
        <div className="space-y-4">
          {ANALYSIS_TOOLS.map((tool) => {
            const ToolIcon = tool.icon;
            return (
              <div
                key={tool.id}
                className="bg-card border border-border rounded-lg overflow-hidden"
              >
                <div className="p-6 flex items-start gap-4">
                  <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
                    <ToolIcon className="w-6 h-6 text-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-foreground mb-1">
                      {t(tool.titleKey)}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {t(tool.descriptionKey)}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity flex items-center gap-2 text-sm shadow-sm cursor-pointer border-none shrink-0"
                    onClick={() => {
                      alert(t("wb_comingSoon"));
                    }}
                  >
                    <Sparkles className="w-4 h-4" />
                    {t("analyze")}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StatCard — single statistic display
// ---------------------------------------------------------------------------

function StatCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="text-3xl font-medium text-foreground mb-1">{value}</div>
      <div className="text-sm text-muted-foreground">{label}</div>
    </div>
  );
}
