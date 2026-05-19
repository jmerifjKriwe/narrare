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
  basic_info: { icon: "Info", color: "text-blue-500" },
  appearance: { icon: "Eye", color: "text-purple-500" },
  personality: { icon: "Heart", color: "text-pink-500" },
  background: { icon: "BookOpen", color: "text-amber-500" },
  relationships: { icon: "Link2", color: "text-green-500" },
  development: { icon: "TrendingUp", color: "text-cyan-500" },
  speech: { icon: "MessageSquare", color: "text-orange-500" },
};

/** Known section icons and accent colors. */
export const SECTION_ICONS: Record<string, { icon: string; color: string }> = {
  background: { icon: "BookOpen", color: "text-amber-500" },
  personality: { icon: "Heart", color: "text-pink-500" },
  appearance: { icon: "Eye", color: "text-purple-500" },
  development: { icon: "TrendingUp", color: "text-cyan-500" },
};

/** Get icon data for a group name, falling back to default. */
export function getGroupIcon(groupName: string): { icon: string; color: string } {
  return GROUP_ICONS[groupName] ?? DEFAULT_ICON;
}

/** Get icon data for a section name, falling back to default. */
export function getSectionIcon(sectionName: string): { icon: string; color: string } {
  return SECTION_ICONS[sectionName] ?? DEFAULT_ICON;
}
