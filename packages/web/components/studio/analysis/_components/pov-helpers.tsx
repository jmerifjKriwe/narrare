/**
 * POV helpers — shared utility functions and tiny display components
 * used across POV sub-components.
 */

import { AlertTriangle } from "lucide-react";
import type { POVIssue } from "@/lib/api/analysis";

// --- Color helpers ---

/** Confidence badge color based on score. */
export function getConfidenceColorClass(confidence: number): string {
  if (confidence >= 0.8)
    return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
  if (confidence >= 0.5)
    return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400";
  return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
}

/** Issue type badge color. */
export function getIssueTypeBadgeClass(type: POVIssue["type"]): string {
  switch (type) {
    case "head_hop":
      return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
    case "knowledge_leak":
      return "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400";
    case "emotional_leak":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400";
    case "physical_impossibility":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400";
  }
}

// --- Tiny display components ---

/** Severity icon + color. */
export function SeverityIcon({ severity }: { severity: POVIssue["severity"] }) {
  if (severity === "error") {
    return <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />;
  }
  return <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0" />;
}
