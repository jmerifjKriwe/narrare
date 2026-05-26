"use client";

/**
 * ScoreRadar — radar/spider chart for beta reader scores.
 *
 * Displays 6 named scores on a 1-10 scale as a radar chart.
 * Uses Recharts RadarChart for SVG-based, responsive rendering.
 * Reusable for future ANAL features with different score dimensions.
 */

import { useTranslations } from "next-intl";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

// --- Score dimensions ---

export interface ScoreDimension {
  key: string;
  value: number;
  label: string;
}

interface ScoreRadarProps {
  /** Score dimensions to display (typically 6). Each has key, value (1-10), label. */
  scores: ScoreDimension[];
  /** Fill color for the radar area. Defaults to primary purple. */
  fillColor?: string;
  /** Stroke color for the radar line. Defaults to primary purple. */
  strokeColor?: string;
}

// --- Component ---

export function ScoreRadar({
  scores,
  fillColor = "hsl(262, 83%, 58%)",
  strokeColor = "hsl(262, 83%, 58%)",
}: ScoreRadarProps) {
  const t = useTranslations("analysis");

  // Map scores to Recharts data format, using labels from props or i18n fallback
  const data = scores.map((s) => ({
    dimension: s.label,
    value: s.value,
    fullMark: 10,
  }));

  return (
    <div className="w-full" role="img" aria-label={t("overall.scores")}>
      <ResponsiveContainer width="100%" height={280}>
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
          <PolarGrid stroke="hsl(var(--border))" />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          />
          <PolarRadiusAxis
            angle={30}
            domain={[0, 10]}
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickCount={6}
          />
          <Radar
            name={t("overall.scores")}
            dataKey="value"
            stroke={strokeColor}
            fill={fillColor}
            fillOpacity={0.2}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

// --- Helper: create score dimensions from BetaReaderOverallAssessment ---

export function createScoreDimensions(
  overall: {
    reader_engagement: number;
    emotional_impact: number;
    pacing_score: number;
    prose_quality: number;
    plot_progression: number;
    character_development: number;
  },
  t: (key: string) => string,
): ScoreDimension[] {
  return [
    { key: "reader_engagement", value: overall.reader_engagement, label: t("overall.engagement") },
    {
      key: "emotional_impact",
      value: overall.emotional_impact,
      label: t("overall.emotionalImpact"),
    },
    { key: "pacing_score", value: overall.pacing_score, label: t("overall.pacing") },
    { key: "prose_quality", value: overall.prose_quality, label: t("overall.proseQuality") },
    {
      key: "plot_progression",
      value: overall.plot_progression,
      label: t("overall.plotProgression"),
    },
    {
      key: "character_development",
      value: overall.character_development,
      label: t("overall.characterDev"),
    },
  ];
}
