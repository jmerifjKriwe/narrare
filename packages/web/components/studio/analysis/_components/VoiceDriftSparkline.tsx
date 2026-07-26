/**
 * VoiceDriftSparkline — inline-SVG per-chapter match-trend line (ANAL-009 γ).
 *
 * Renders the always-visible trend (signal i) as a polyline with one coloured
 * dot per chapter (coloured by band) plus dashed ⚡ jump-guide lines at the
 * chapters where a metric jumped (signal iii). Purely presentational —
 * mirrors the approved mockup's `.spark` SVG.
 *
 * Accessibility: the SVG carries an `aria-label` describing the trend shape;
 * the underlying per-chapter numbers remain available to assistive tech via
 * the sibling chapter strip in the detail card.
 *
 * @module VoiceDriftSparkline
 */

import type { JumpPoint, TrendPoint, VoiceDriftBand } from "@/lib/api/voice-drift-stream";
import { DRIFT_BANDS } from "./voice-drift-bands";

interface VoiceDriftSparklineProps {
  /** Per-chapter match trend (signal i), in chapter order. */
  trend: TrendPoint[];
  /** Adjacent-chapter jumps (signal iii) — drawn as dashed guides at the `to` chapter. */
  jumps: JumpPoint[];
  /** Accessible description of the trend shape (e.g. "declining", "flat"). */
  ariaLabel: string;
}

// SVG viewBox geometry — matches the approved mockup's coordinate space.
const VIEW_WIDTH = 120;
const VIEW_HEIGHT = 30;
const PADDING = 6;
const BOTTOM = 27;

/** Map a [0, 100] match score to an SVG Y coordinate (100 = top, 0 = bottom). */
function scoreToY(score: number): number {
  const top = 3;
  const usable = BOTTOM - top;
  // Higher score = higher on the chart (lower Y). Clamp to the usable band.
  const clamped = Math.min(100, Math.max(0, score));
  return BOTTOM - (clamped / 100) * usable;
}

/** Map a point index [0, n-1] to an SVG X coordinate across the viewBox. */
function indexToX(index: number, count: number): number {
  if (count <= 1) return VIEW_WIDTH / 2;
  const usable = VIEW_WIDTH - PADDING * 2;
  return PADDING + (index / (count - 1)) * usable;
}

/** Band → fill colour token for the dot (Tailwind hex-free: use currentColor via class on the svg). */
const BAND_FILL: Record<VoiceDriftBand, string> = {
  stable: "#10b981", // emerald-500
  minor: "#eab308", // yellow-500
  moderate: "#f97316", // orange-500
  major: "#ef4444", // red-500
};

export function VoiceDriftSparkline({ trend, jumps, ariaLabel }: VoiceDriftSparklineProps) {
  if (trend.length === 0) return null;

  const points = trend.map((p, i) => ({
    x: indexToX(i, trend.length),
    y: scoreToY(p.match_subscore),
    band: p.band,
  }));

  const polyline = points.map((p) => `${p.x},${p.y.toFixed(2)}`).join(" ");

  // Jump guides land at the `to_chapter_id` column of the trend.
  const chapterIndex = new Map(trend.map((p, i) => [p.chapter_id, i]));
  const jumpGuides = jumps
    .map((j) => chapterIndex.get(j.to_chapter_id))
    .filter((idx): idx is number => idx != null);

  return (
    <svg
      className="block h-auto w-full max-w-[240px] overflow-visible"
      viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
      role="img"
      aria-label={ariaLabel}
    >
      {/* baseline */}
      <line
        x1="0"
        y1={BOTTOM}
        x2={VIEW_WIDTH}
        y2={BOTTOM}
        stroke="currentColor"
        strokeWidth={0.6}
        className="text-border"
      />
      {/* jump guides */}
      {jumpGuides.map((idx) => {
        const x = indexToX(idx, trend.length);
        const y = points[idx]?.y ?? BOTTOM;
        const chapterId = trend[idx]?.chapter_id ?? `idx-${idx}`;
        return (
          <g key={`jump-${chapterId}`}>
            <line
              x1={x}
              y1={2}
              x2={x}
              y2={BOTTOM + 1}
              stroke="#f0c14b"
              strokeWidth={0.7}
              strokeDasharray="2 2"
              opacity={0.5}
            />
            <circle cx={x} cy={y} r={1.4} fill="#f0c14b" />
          </g>
        );
      })}
      {/* trend line */}
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth={1.3}
        strokeLinejoin="round"
        strokeLinecap="round"
        className="text-muted-foreground"
        points={polyline}
      />
      {/* per-chapter dots (coloured by band) */}
      {points.map((p, i) => (
        <circle
          key={`pt-${trend[i].chapter_id}`}
          cx={p.x}
          cy={p.y}
          r={2.1}
          fill={BAND_FILL[p.band]}
        />
      ))}
    </svg>
  );
}
