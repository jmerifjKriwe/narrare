import type { LucideIcon } from "lucide-react";
import {
  BookOpen,
  Brain,
  FileText,
  Info,
  Keyboard,
  Settings2,
  Sparkles,
  Target,
} from "lucide-react";

export type SettingsCategory =
  | "novel-details"
  | "general"
  | "writing"
  | "ai"
  | "prompts"
  | "kb-templates"
  | "learning"
  | "shortcuts"
  | "about";

export interface CategoryConfig {
  id: SettingsCategory;
  icon: LucideIcon;
  labelKey: string;
}

export interface StaticShortcut {
  key: string;
  labelKey: string;
  descKey: string;
}

export interface TranslatedShortcut {
  keyKey: string;
  labelKey: string;
  descKey: string;
}

export type ShortcutConfig = StaticShortcut | TranslatedShortcut;

export const SETTINGS_CATEGORIES: CategoryConfig[] = [
  { id: "novel-details", icon: BookOpen, labelKey: "settings.novelDetails" },
  { id: "general", icon: Settings2, labelKey: "settings.general" },
  { id: "writing", icon: Target, labelKey: "settings.writingGoals" },
  { id: "ai", icon: Sparkles, labelKey: "settings.aiSetup" },
  { id: "prompts", icon: FileText, labelKey: "settings.promptsTab" },
  { id: "kb-templates", icon: BookOpen, labelKey: "settings.kbTemplates" },
  { id: "learning", icon: Brain, labelKey: "settings.learning" },
  { id: "shortcuts", icon: Keyboard, labelKey: "settings.shortcuts" },
  { id: "about", icon: Info, labelKey: "settings.about" },
];

export const SETTINGS_SHORTCUTS: ShortcutConfig[] = [
  {
    key: "Cmd+S",
    labelKey: "settings.shortcutsSection.save",
    descKey: "settings.shortcutsSection.saveDescription",
  },
  {
    key: "Cmd+N",
    labelKey: "settings.shortcutsSection.newChapter",
    descKey: "settings.shortcutsSection.newChapterDescription",
  },
  {
    key: "Cmd+K",
    labelKey: "settings.shortcutsSection.commandPalette",
    descKey: "settings.shortcutsSection.commandPaletteDescription",
  },
  {
    key: "Ctrl+B",
    labelKey: "settings.shortcutsSection.bold",
    descKey: "settings.shortcutsSection.boldDescription",
  },
  {
    key: "Ctrl+I",
    labelKey: "settings.shortcutsSection.italic",
    descKey: "settings.shortcutsSection.italicDescription",
  },
  {
    keyKey: "settings.shortcutsSection.selectText",
    labelKey: "settings.shortcutsSection.aiRewrite",
    descKey: "settings.shortcutsSection.aiRewriteDescription",
  },
  {
    key: "Tab",
    labelKey: "settings.shortcutsSection.ghostTextAccept",
    descKey: "settings.shortcutsSection.ghostTextAcceptDescription",
  },
  {
    key: "→",
    labelKey: "settings.shortcutsSection.ghostTextWord",
    descKey: "settings.shortcutsSection.ghostTextWordDescription",
  },
  {
    key: "Esc",
    labelKey: "settings.shortcutsSection.ghostTextDismiss",
    descKey: "settings.shortcutsSection.ghostTextDismissDescription",
  },
];

export const ABOUT_FEATURE_KEYS = [
  "settings.aboutSection.feature1",
  "settings.aboutSection.feature2",
  "settings.aboutSection.feature3",
  "settings.aboutSection.feature4",
  "settings.aboutSection.feature5",
] as const;
