import type {
  ConsistencyCheckType,
  ConsistencyIssue,
  ConsistencySeverity,
} from "@/lib/api/analysis";

export const SEVERITY_STYLES: Record<ConsistencySeverity, string> = {
  error: "bg-red-100 text-red-700 dark:bg-red-950/30 dark:text-red-400",
  warning: "bg-amber-100 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400",
  info: "bg-blue-100 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400",
};

export const SEVERITY_DOT: Record<ConsistencySeverity, string> = {
  error: "bg-red-500",
  warning: "bg-amber-500",
  info: "bg-blue-500",
};

export const SEVERITY_BORDER: Record<ConsistencySeverity, string> = {
  error: "border-l-red-400 dark:border-l-red-500",
  warning: "border-l-amber-400 dark:border-l-amber-500",
  info: "border-l-blue-400 dark:border-l-blue-500",
};

export const CHECK_TYPE_LABELS: Record<ConsistencyCheckType, string> = {
  character: "Character",
  timeline: "Timeline",
  world: "World",
  plot: "Plot",
};

export const CHECK_TYPE_STYLES: Record<ConsistencyCheckType, string> = {
  character: "bg-purple-100 text-purple-700 dark:bg-purple-950/30 dark:text-purple-400",
  timeline: "bg-blue-100 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400",
  world: "bg-teal-100 text-teal-700 dark:bg-teal-950/30 dark:text-teal-400",
  plot: "bg-orange-100 text-orange-700 dark:bg-orange-950/30 dark:text-orange-400",
};

export function issueKey(issue: ConsistencyIssue): string {
  return `${issue.description}::${issue.locations.join(",")}`;
}
