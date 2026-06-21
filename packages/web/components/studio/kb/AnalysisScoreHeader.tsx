"use client";

/**
 * AnalysisScoreHeader — Score display for worldbuilding analysis results.
 *
 * Shows the worldbuilding score, progress bar, and overall assessment.
 */

import { useTranslations } from "next-intl";
import type { WorldbuildingAnalysisResponse } from "@/lib/api/worldbuilding";

interface AnalysisScoreHeaderProps {
  readonly analysis: WorldbuildingAnalysisResponse;
}

export function AnalysisScoreHeader({ analysis }: AnalysisScoreHeaderProps) {
  const t = useTranslations("studio");

  return (
    <div className="flex items-start gap-4 p-4 border-b border-border bg-muted/30">
      <div className="flex-shrink-0 flex flex-col items-center">
        <div className="text-2xl font-bold text-purple-500">
          {analysis.worldbuilding_score.toFixed(2)}
        </div>
        <div className="text-xs text-muted-foreground">{t("worldbuilding.score")}</div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="w-full h-2 bg-muted rounded-full overflow-hidden mb-2">
          <div
            className="h-full bg-purple-500 rounded-full transition-all duration-500"
            style={{ width: `${Math.round(analysis.worldbuilding_score * 100)}%` }}
          />
        </div>
        <p className="text-sm text-muted-foreground line-clamp-2">{analysis.overall_assessment}</p>
        <p className="text-xs text-muted-foreground mt-1">
          {t("worldbuilding.entityCount", { count: analysis.entity_count })}
        </p>
      </div>
    </div>
  );
}
