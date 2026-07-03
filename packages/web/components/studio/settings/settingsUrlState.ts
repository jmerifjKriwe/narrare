import { SETTINGS_CATEGORIES, type SettingsCategory } from "./settings-view-config";

const SETTINGS_CATEGORY_IDS = new Set<SettingsCategory>(
  SETTINGS_CATEGORIES.map((category) => category.id),
);

export const DEFAULT_SETTINGS_CATEGORY: SettingsCategory = "novel-details";

export function parseSettingsCategory(value: string | null): SettingsCategory {
  if (value !== null && SETTINGS_CATEGORY_IDS.has(value as SettingsCategory))
    return value as SettingsCategory;
  return DEFAULT_SETTINGS_CATEGORY;
}

export function serializeSettingsCategory(category: SettingsCategory): string | null {
  return category === DEFAULT_SETTINGS_CATEGORY ? null : category;
}
