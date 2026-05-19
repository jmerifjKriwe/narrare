/**
 * Group → icon/color maps for KB template field groups and sections.
 *
 * Maps template field_group/section names to UI metadata (icons, colors).
 * Unknown group/section names get a default fallback.
 */

// Default fallback icon data
const DEFAULT_ICON = { icon: "FileText", color: "text-muted-foreground" };

/** Known field group icons and accent colors. */
export const GROUP_ICONS: Record<string, { icon: string; color: string }> = {
  // Character groups
  basic_info: { icon: "Info", color: "text-blue-500" },
  appearance: { icon: "Eye", color: "text-purple-500" },
  personality: { icon: "Heart", color: "text-pink-500" },
  background: { icon: "BookOpen", color: "text-amber-500" },
  relationships: { icon: "Link2", color: "text-green-500" },
  development: { icon: "TrendingUp", color: "text-cyan-500" },
  speech: { icon: "MessageSquare", color: "text-orange-500" },

  // Location groups
  features: { icon: "TreePine", color: "text-emerald-500" },
  inhabitants: { icon: "Users", color: "text-violet-500" },

  // Faction groups
  structure: { icon: "Network", color: "text-indigo-500" },
  belief_system: { icon: "Sparkles", color: "text-yellow-500" },

  // Object groups
  properties: { icon: "Wrench", color: "text-slate-500" },
  origin_details: { icon: "Clock", color: "text-teal-500" },
  significance: { icon: "Star", color: "text-amber-500" },

  // System groups
  mechanics: { icon: "Cog", color: "text-zinc-500" },
  practitioner_details: { icon: "GraduationCap", color: "text-blue-400" },
  origins: { icon: "Scroll", color: "text-stone-500" },

  // Timeline groups
  period: { icon: "Calendar", color: "text-rose-500" },
  events: { icon: "Zap", color: "text-orange-500" },

  // Setting groups
  basics: { icon: "Info", color: "text-blue-500" },
  world_rules: { icon: "Scale", color: "text-purple-500" },
  society: { icon: "Building", color: "text-green-500" },
  geography: { icon: "Map", color: "text-teal-500" },

  // Concept groups
  definition: { icon: "BookMarked", color: "text-blue-500" },

  // Shared group (faction, location, object)
  history: { icon: "Clock", color: "text-amber-500" },
};

/** Known section icons and accent colors. */
export const SECTION_ICONS: Record<string, { icon: string; color: string }> = {
  background: { icon: "BookOpen", color: "text-amber-500" },
  personality: { icon: "Heart", color: "text-pink-500" },
  appearance: { icon: "Eye", color: "text-purple-500" },
  development: { icon: "TrendingUp", color: "text-cyan-500" },
  description: { icon: "FileText", color: "text-muted-foreground" },
  notes: { icon: "StickyNote", color: "text-muted-foreground" },
  implications: { icon: "Lightbulb", color: "text-yellow-500" },
  world_description: { icon: "Globe", color: "text-blue-500" },
};

/** Get icon data for a group name, falling back to default. */
export function getGroupIcon(groupName: string): { icon: string; color: string } {
  return GROUP_ICONS[groupName] ?? DEFAULT_ICON;
}

/** Get icon data for a section name, falling back to default. */
export function getSectionIcon(sectionName: string): { icon: string; color: string } {
  return SECTION_ICONS[sectionName] ?? DEFAULT_ICON;
}
