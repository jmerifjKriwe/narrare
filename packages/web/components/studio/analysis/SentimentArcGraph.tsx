"use client";

/**
 * SentimentArcGraph — cross-chapter VAD line chart for SentimentPanel.
 *
 * Extracted from SentimentPanel to comply with RULE-04 (400-line limit).
 * Shows valence, arousal, and dominance trajectories across chapters.
 * Only rendered when 2+ chapters have been analyzed.
 */

import { useTranslations } from "next-intl";
import { Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SentimentOverview } from "@/lib/api/analysis";

// --- Types ---

interface SentimentArcGraphProps {
  /** Per-chapter sentiment results. Must contain >= 2 entries. */
  results: SentimentOverview[];
}

interface ArcTooltipEntry {
  value: number;
  dataKey: string;
  color: string;
}

interface ArcTooltipProps {
  active?: boolean;
  payload?: ArcTooltipEntry[];
  label?: string;
}

// --- Custom Tooltip ---

function ArcTooltipContent({ active, payload, label }: ArcTooltipProps) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-card border border-border rounded-lg p-2.5 shadow-md" role="tooltip">
      <p className="text-xs font-semibold mb-1.5">{label}</p>
      <div className="space-y-1">
        {payload.map((entry) => (
          <div key={entry.dataKey} className="flex items-center gap-1.5 text-xs">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-muted-foreground capitalize">{entry.dataKey}:</span>
            <span className="font-medium">{Number(entry.value).toFixed(3)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Component ---

export function SentimentArcGraph({ results }: SentimentArcGraphProps) {
  const t = useTranslations("analysis");

  const arcData = results.map((r, idx) => ({
    chapter: t("sentiment.chapter", { number: idx + 1 }),
    valence: r.average_vad.valence,
    arousal: r.average_vad.arousal,
    dominance: r.average_vad.dominance,
  }));

  return (
    <section aria-label={t("sentiment.arcTrajectory")}>
      <h4 className="text-sm font-medium mb-3">{t("sentiment.arcTrajectory")}</h4>
      <div className="rounded-lg border border-border p-3 bg-card">
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={arcData} margin={{ left: 0, right: 16, top: 4, bottom: 4 }}>
            <XAxis
              dataKey="chapter"
              tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            />
            <YAxis domain={[-1, 1]} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
            <Tooltip content={<ArcTooltipContent />} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="valence" stroke="#3b82f6" dot strokeWidth={2} />
            <Line type="monotone" dataKey="arousal" stroke="#f59e0b" dot strokeWidth={2} />
            <Line type="monotone" dataKey="dominance" stroke="#22c55e" dot strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
