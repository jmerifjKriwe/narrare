/**
 * Shared helper functions for readability analysis sub-components.
 *
 * Score-based color utilities used across MetricCard, ScoreBar, and
 * SentenceRow components.
 */

/**
 * Returns a Tailwind text-color class based on readability score.
 * ≥60 → green, ≥30 → yellow, <30 → red.
 */
export function getScoreColorClass(score: number): string {
  if (score >= 60) return "text-green-600 dark:text-green-400";
  if (score >= 30) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
}

/**
 * Returns a Tailwind background-color class for score bars.
 * ≥60 → green, ≥30 → yellow, <30 → red.
 */
export function getScoreBarClass(score: number): string {
  if (score >= 60) return "bg-green-500";
  if (score >= 30) return "bg-yellow-500";
  return "bg-red-500";
}
