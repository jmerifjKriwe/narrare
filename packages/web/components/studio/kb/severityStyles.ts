/**
 * Shared severity badge color styles for KB analysis cards.
 *
 * Extracted so individual card components (GapCard, ConsistencyCard) can
 * import without a circular dependency on WorldbuildingAnalysisCards.
 */

export const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  major: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  minor: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  info: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
};
