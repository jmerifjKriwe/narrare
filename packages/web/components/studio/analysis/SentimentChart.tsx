"use client";

/**
 * SentimentChart — emotion bar chart for SentimentPanel.
 *
 * Extracted from SentimentPanel to keep it under RULE-04 limit.
 * Uses Recharts BarChart for SVG-based, responsive rendering.
 * Shows emotion scores as horizontal bars with detailed hover tooltips.
 */

import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EmotionScores } from "@/lib/api/analysis";

// --- Emotion display config ---

interface EmotionConfig {
  key: keyof EmotionScores;
  label: string;
  color: string;
}

const EMOTION_CONFIG: EmotionConfig[] = [
  { key: "joy", label: "Joy", color: "hsl(45, 93%, 47%)" },
  { key: "trust", label: "Trust", color: "hsl(142, 71%, 45%)" },
  { key: "anticipation", label: "Anticipation", color: "hsl(30, 90%, 55%)" },
  { key: "surprise", label: "Surprise", color: "hsl(270, 60%, 55%)" },
  { key: "fear", label: "Fear", color: "hsl(260, 50%, 55%)" },
  { key: "sadness", label: "Sadness", color: "hsl(210, 50%, 55%)" },
  { key: "anger", label: "Anger", color: "hsl(0, 72%, 55%)" },
  { key: "disgust", label: "Disgust", color: "hsl(120, 40%, 40%)" },
  { key: "positive", label: "Positive", color: "hsl(142, 71%, 55%)" },
  { key: "negative", label: "Negative", color: "hsl(0, 60%, 55%)" },
];

// --- Types ---

interface SentimentChartProps {
  /** Emotion scores to display as a bar chart. */
  emotions: EmotionScores;
}

interface EmotionTooltipPayloadEntry {
  value: number;
  payload: { name: string; fill: string };
}

interface EmotionTooltipContentProps {
  active?: boolean;
  payload?: EmotionTooltipPayloadEntry[];
}

// --- Custom Tooltip (ANAL-002 #5) ---

function EmotionTooltipContent({ active, payload }: EmotionTooltipContentProps) {
  if (!active || !payload?.length) return null;

  const entry = payload[0];
  const emotionName = entry.payload.name;
  const score = Number(entry.value);

  return (
    <div className="bg-card border border-border rounded-lg p-2.5 shadow-md" role="tooltip">
      <p className="text-xs font-semibold mb-1">{emotionName}</p>
      <div className="flex items-center gap-2">
        <div
          className="h-2 rounded-full"
          style={{
            backgroundColor: entry.payload.fill,
            width: `${Math.max(score * 100, 4)}%`,
            minWidth: "4px",
            maxWidth: "100px",
          }}
        />
        <span className="text-xs text-muted-foreground font-mono">{score.toFixed(3)}</span>
      </div>
    </div>
  );
}

// --- Component ---

export function SentimentChart({ emotions }: SentimentChartProps) {
  const data = EMOTION_CONFIG.map(({ key, label, color }) => ({
    name: label,
    value: emotions[key],
    fill: color,
  })).sort((a, b) => b.value - a.value);

  return (
    <div className="w-full" role="img" aria-label="Emotion scores">
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} layout="vertical" margin={{ left: 0, right: 16, top: 4, bottom: 4 }}>
          <XAxis
            type="number"
            domain={[0, 1]}
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickCount={6}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={80}
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          />
          <Tooltip content={<EmotionTooltipContent />} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={20}>
            {data.map((entry) => (
              <rect key={entry.name} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
