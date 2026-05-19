/**
 * KB Entity type configuration constants.
 *
 * Shared across all KB sub-components.
 */

import {
  BookOpen,
  Clock,
  Globe,
  type LucideIcon,
  MapPin,
  Package,
  Shield,
  User,
  Zap,
} from "lucide-react";
import type { KBEntityType } from "@/lib/api/kb";

/** The 8 entity types supported by the KB system. */
export const ENTITY_TYPES: KBEntityType[] = [
  "character",
  "concept",
  "faction",
  "location",
  "object",
  "setting",
  "system",
  "timeline",
];

/** Map entity type → lucide icon. */
export const TYPE_ICONS: Record<KBEntityType, LucideIcon> = {
  character: User,
  concept: BookOpen,
  faction: Shield,
  location: MapPin,
  object: Package,
  setting: Globe,
  system: Zap,
  timeline: Clock,
};

/** i18n key suffix for each entity type label. */
export const TYPE_LABEL_KEYS: Record<KBEntityType, string> = {
  character: "kb.characters",
  concept: "kb.concepts",
  faction: "kb.factions",
  location: "kb.locations",
  object: "kb.objects",
  setting: "kb.settings",
  system: "kb.systems",
  timeline: "kb.timelines",
};

/** Status badge color classes. */
export const STATUS_COLORS: Record<string, string> = {
  draft: "bg-muted text-muted-foreground",
  reviewed: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  canon: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  deprecated: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
};

/** Relative time formatter (simplified, client-only). */
export function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  return new Date(dateStr).toLocaleDateString();
}
