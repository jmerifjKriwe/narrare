/**
 * Shared constants and helpers for KB improve suggestions.
 *
 * Type icons, color maps, and label formatting used across
 * improve panel sub-components.
 */

import { Expand, Link2, PlusCircle, Shuffle, Sparkles } from "lucide-react";
import type { ComponentType } from "react";

/** Icon map for suggestion types. */
export const TYPE_ICONS: Record<string, ComponentType<{ className?: string }>> = {
  add_field: PlusCircle,
  connect: Link2,
  expand: Expand,
  reorganize: Shuffle,
};

/** Color classes for suggestion type badges. */
export const TYPE_COLORS: Record<string, string> = {
  add_field: "text-blue-500 bg-blue-100 dark:bg-blue-900/30",
  connect: "text-purple-500 bg-purple-100 dark:bg-purple-900/30",
  expand: "text-green-500 bg-green-100 dark:bg-green-900/30",
  reorganize: "text-amber-500 bg-amber-100 dark:bg-amber-900/30",
};

/** Fallback icon when type is unknown. */
export const DEFAULT_ICON = Sparkles;

/** Default color classes when type is unknown. */
export const DEFAULT_COLOR_CLASS = "text-gray-500 bg-gray-100";

/**
 * Format a suggestion type into a human-readable label.
 *
 * Uses the translation function to look up a localised label,
 * falling back to a pretty-printed version of the raw type key.
 */
export function getTypeLabel(type: string, t: (key: string) => string): string {
  const key = `kb.improve.type.${type}`;
  const v = t(key);
  return v !== key ? v : type.replace(/_/g, " ");
}
