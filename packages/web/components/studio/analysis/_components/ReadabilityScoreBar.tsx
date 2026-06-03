/**
 * ReadabilityScoreBar — horizontal progress bar for a readability score.
 *
 * Displays a label, numeric score, and colored fill bar.
 * Color is derived from the score via shared helpers.
 */

import { getScoreBarClass, getScoreColorClass } from "./readability-helpers";

interface ScoreBarProps {
  label: string;
  score: number;
  maxScore?: number;
}

export function ReadabilityScoreBar({ label, score, maxScore = 100 }: ScoreBarProps) {
  const percentage = Math.min(100, Math.max(0, (score / maxScore) * 100));

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className={`text-xs font-medium ${getScoreColorClass(score)}`}>
          {score.toFixed(1)}
        </span>
      </div>
      <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${getScoreBarClass(score)}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
